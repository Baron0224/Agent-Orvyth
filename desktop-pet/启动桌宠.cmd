@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist node_modules (
  echo 第一次运行，正在安装依赖（Electron 约 100MB，可能要几分钟）...
  call npm install
  if errorlevel 1 (
    echo.
    echo 安装失败。可以换国内镜像后重试：
    echo   npm config set registry https://registry.npmmirror.com
    echo   set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
    pause
    exit /b 1
  )
)
call npm start
