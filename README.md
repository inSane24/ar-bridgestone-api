# OCR API (FastAPI)

**OCR用のHTTPサーバー** を立てて動かすための最小構成です。

## 起動

```bash
python main.py
```

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

## 運用メモ

- `--host 0.0.0.0` は同一ネットワークからアクセス可能になります（必要な範囲に限定・FW設定推奨）。
- 初回起動時にモデルの準備で時間がかかる場合があります。
