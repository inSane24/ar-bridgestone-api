@echo off
echo Running WSL portproxy setup...
powershell -ExecutionPolicy Bypass -File "%~dp0setup-portproxy.ps1" -Port 8000
echo.
pause