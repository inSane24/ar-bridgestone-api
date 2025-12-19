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

## Windows（WSL2）環境でのネットワーク設定（推奨）

この API を **WSL2 上で起動する場合**、WSL の IP アドレスは再起動のたびに変わります。  
同じネットワーク上の別 PC から API を利用できるようにするため、付属の PowerShell スクリプトを使って  
**portproxy の設定** と **Windows Firewall の開放** を自動化します。

### 使い方

1. Windows 側で **右クリック →「管理者として実行」** します。
   ```
   cd C:\tools
   powershell -ExecutionPolicy Bypass -File .\setup-portproxy.ps1 -Port 8000
   ```

2. WSL 上で API サーバーを起動します。

   ```bash
   python main.py
   ```

3. 同じネットワーク上の別 PC / 端末から以下にアクセスします。

   ```
   http://<Windows の IP アドレス>:8000/docs
   ```

- ファイアウォールルールは **初回実行時のみ作成** され、2回目以降は再利用されます。
- WSL を再起動した場合は、このスクリプトを再度実行してください。