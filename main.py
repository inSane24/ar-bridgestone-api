# 起動方法
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# http://localhost:8000/docs

from __future__ import annotations

import os
from pathlib import Path
import threading
from typing import Iterable, List, Dict, Any, Optional
import socket
import subprocess
import sys
from contextlib import contextmanager

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from onnxocr.onnx_paddleocr import ONNXPaddleOcr
import uvicorn


@contextmanager
def _suppress_stdout_stderr() -> Iterable[None]:
    """Temporarily silence stdout/stderr (for noisy OCR init)."""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    try:
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

def _init_ocr() -> ONNXPaddleOcr:
    """Create a single OCR instance to reuse across requests."""
    try:
        use_gpu = _env_bool("USE_GPU", True)
        with _suppress_stdout_stderr():
            return ONNXPaddleOcr(use_gpu=use_gpu, lang="english")
    except Exception as exc:  # pragma: no cover - only runs at startup
        raise RuntimeError("Failed to initialize ONNXPaddleOcr") from exc


ocr = _init_ocr()
_ocr_lock = threading.Lock()
app = FastAPI(title="ONNX PaddleOCR API", version="1.0.0")


def _format_results(raw: Iterable) -> List[Dict[str, Any]]:
    """Convert PaddleOCR-style results into a JSON-serializable list."""
    formatted: List[Dict[str, Any]] = []
    for detections in raw:
        for box, (text, score) in detections:
            formatted.append(
                {
                    "text": text,
                    "score": float(score),
                    "box": [[float(x), float(y)] for x, y in box],
                }
            )
    return formatted


def run_ocr_from_path(image_path: Path) -> List[Dict[str, Any]]:
    """Run OCR given an image path."""
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    data = image_path.read_bytes()
    return run_ocr_from_bytes(data)


def run_ocr_from_bytes(image_bytes: bytes) -> List[Dict[str, Any]]:
    """Decode raw image bytes and run OCR."""
    if not image_bytes:
        raise ValueError("Empty image data")

    img = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")

    with _ocr_lock:
        raw = ocr.ocr(img)
    return _format_results(raw)


def _is_wsl() -> bool:
    if os.getenv("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/sys/kernel/osrelease", "r", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def _windows_host_ip() -> Optional[str]:
    """Retrieve the Windows host LAN IP when running under WSL."""
    try:
        powershell_cmd = (
            "$ErrorActionPreference='Stop';"
            "$route=Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
            "Sort-Object RouteMetric | Select-Object -First 1;"
            "if($route){"
            " $ip=Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 | "
            "   Where-Object { $_.IPAddress -notmatch '^169\\.254\\.' } | Select-Object -First 1;"
            " if($ip){[Console]::OutputEncoding=[Text.UTF8Encoding]::UTF8;$ip.IPAddress}"
            "}"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", powershell_cmd],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        completed = None

    if completed and completed.stdout:
        ip = completed.stdout.decode("utf-8", errors="ignore").strip()
        if ip:
            return ip

    resolv_conf = Path("/etc/resolv.conf")
    try:
        for line in resolv_conf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("nameserver"):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except OSError:
        pass
    return None


def _preferred_ip() -> str:
    """Return the IP address we recommend for accessing FastAPI."""
    try:
        # UDP connect doesn't actually send traffic, but reveals the active interface.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip:
                return ip
    except OSError:
        pass

    host_name = socket.gethostname().strip() or "localhost"
    try:
        ip = socket.gethostbyname(host_name)
        if ip:
            return ip
    except OSError:
        pass

    return "127.0.0.1"


def _print_access_tips(port: int) -> None:
    ip_address: Optional[str] = None
    if _is_wsl():
        ip_address = _windows_host_ip()
    if not ip_address:
        ip_address = _preferred_ip()
    print(f"アクセス用IPアドレス: {ip_address}")
    print(f"http://{ip_address}:{port}/ocr")



@app.get("/")
def root() -> Dict[str, str]:
    return {"service": "onnx-ocr-api", "docs": "/docs", "healthz": "/healthz"}


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/ocr")
def ocr_endpoint(file: UploadFile = File(...)) -> Dict[str, Any]:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    data = file.file.read()
    try:
        detections = run_ocr_from_bytes(data)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}") from exc

    return {"detections": detections}


def sample(image_path: Path = Path("sample.png")) -> None:
    """Run the local sample (mirrors the request style in the prompt)."""
    for item in run_ocr_from_path(image_path):
        print(f"text: {item['text']}, score: {item['score']}")


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = _env_bool("RELOAD", False)
    log_level = os.getenv("LOG_LEVEL", "warning")
    if host == "0.0.0.0":
        _print_access_tips(port)
    else:
        print(f"FastAPI を http://{host}:{port} で待ち受けます。")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=log_level,
    )
