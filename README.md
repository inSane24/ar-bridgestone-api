# OCR API (FastAPI)

**OCR用のHTTPサーバー** を立てて動かすための最小構成です。

## 起動

```bash
python main.py
```

- GPUが利用できる環境ではデフォルトでGPUを使用します。CPUで実行したい場合は `USE_GPU=0 python main.py` としてください。

## 使い方（例）

```bash
curl -X POST http://localhost:8000/ocr \
  -F "file=@./sample.png"
```

返り値例:

```json
{
  "detections": [
    {
      "text": "A8-5",
      "score": 0.99,
      "box": [[...], ...]
    }
  ]
}
```

## Windows 側ネットワーク設定の自動化

WSL の IP は再起動などで変わるため、以下の PowerShell スクリプトで **IP 確認 → PortProxy 設定 → Firewall 開放** をまとめて実行できます。

```powershell
# 管理者 PowerShell / コマンドプロンプトで
cd <このリポジトリ>
.\setup-portproxy.bat
```

- 初回実行時にファイアウォールルールを作成し、2回目以降は再利用します。