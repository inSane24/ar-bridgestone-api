# 起動方法
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# http://localhost:8000/docs

from __future__ import annotations

import os
from pathlib import Path
import threading
from typing import Iterable, List, Dict, Any

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from onnxocr.onnx_paddleocr import ONNXPaddleOcr
import uvicorn


def _init_ocr() -> ONNXPaddleOcr:
    """Create a single OCR instance to reuse across requests."""
    try:
        return ONNXPaddleOcr(use_gpu=False, lang="english")
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
    uvicorn.run("main:app", host=host, port=port, reload=True)
