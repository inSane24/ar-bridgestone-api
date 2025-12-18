@echo off
setlocal
set PORT=%1
if "%PORT%"=="" set PORT=8000
set RULE_NAME=WSL FastAPI %PORT%

echo PortProxy + Firewall をポート %PORT% で設定します...
powershell -ExecutionPolicy Bypass -File "%~dp0setup-portproxy.ps1" -Port %PORT% -RuleName "%RULE_NAME%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo エラーが発生しました。管理者権限で実行しているか確認してください。
    exit /b %ERRORLEVEL%
)

echo.
echo 完了しました。必要に応じて FastAPI を起動し http://localhost:%PORT% などでアクセスしてください。
endlocal
