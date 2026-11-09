@echo off
chcp 65001 >nul
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0cloud_launch.py" %*
) else (
    py -3 -X utf8 "%~dp0cloud_launch.py" %*
)
if errorlevel 1 pause
