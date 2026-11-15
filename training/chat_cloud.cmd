@echo off
chcp 65001 >nul
if /I "%~1"=="--forget-key" goto credentials
echo 云端聊天已并入 8775。请在 Orvyth 网页设置里选择云端聊天。
call "%~dp0chat_web.cmd"
exit /b %errorlevel%
:credentials
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0cloud_launch.py" %*
) else (
    py -3 -X utf8 "%~dp0cloud_launch.py" %*
)
if errorlevel 1 pause
