# Orvyth 桌面小柴（desktop-pet）

一个真正住在 Windows 桌面上的小柴犬：透明悬浮窗、置顶、可拖动，复用
`training/companion-preview/dog/3d/model.js` 的程序化 3D 模型，不复制、不下载任何模型文件。
右键可以跟它说话，说的话走本机 `chat_web.py` 的 `/api/chat`。

## 运行

需要 Node.js 18+（自带 npm）。

```bat
cd D:\Codex\Orvyth\desktop-pet
npm install
npm start
```

或者直接双击 `启动桌宠.cmd`（第一次会自动装依赖）。

依赖只有 Electron。首次 `npm install` 要下载约 100MB 的 Electron 二进制，国内网络慢的话：

```bat
npm config set registry https://registry.npmmirror.com
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
```

## 怎么玩

| 操作 | 效果 |
| --- | --- |
| 按住拖动 | 把小柴拖到桌面任意位置 |
| 单击 | 摸摸它，冒一句随机的话 |
| 双击 | 打开网页版 Orvyth 聊天页（默认 `http://127.0.0.1:8775/`） |
| 右键 | 菜单：说点什么 / 打开聊天页 / 退出桌宠 |
| 右键 → 说点什么 | 命令行输入，回车发送，回复流式显示在气泡里 |
| 鼠标划过空白处 | 自动点击穿透，不挡下面窗口的操作 |

兜底快捷键：**Ctrl+Shift+O**，强制恢复窗口可点击并置顶（万一穿透状态卡住，窗口点不到时用它）。

## 聊天部分

- 端口默认 8775（`chat_web.py` 的默认值），可以用环境变量覆盖：`set ORVYTH_PORT=8800 && npm start`。
- 需要先启动网页版：跑 `training\chat_web.cmd`，让 `chat_web.py` 在监听。
- 桌宠会先 `GET /api/session` 拿到本机 owner 和 `active_chat`，再 `POST /api/chat`；
  消息会写进**当前这段聊天**，网页里能看到同一条对话（这是故意的，保持同一个 Orvyth）。
- 8B 模型首字可能要几秒，气泡会先显示「……」。

## 目录

```
desktop-pet/
  main.js            主进程：透明窗口、自定义协议 pet://、拖拽、聊天 HTTP 客户端
  preload.js         contextBridge 暴露给渲染层的 5 个方法
  renderer/
    index.html       透明页面
    pet.css          气泡 / 输入框 / 右键菜单
    pet.js           Three.js 场景、模型加载、看鼠标、眨眼、摇头摆尾、交互
  启动桌宠.cmd        双击启动（缺依赖时自动安装）
```

模型路径（相对本目录）：

```
../training/companion-preview/dog/3d/model.js
../training/companion-preview/dog/3d/vendor/three.module.js
```

`main.js` 里注册了 `pet://local/` 协议，根目录是仓库根 `D:\Codex\Orvyth`，
所以渲染层可以直接 `import '../../training/...'`，改 `companion-preview` 后桌宠会一起变。

## 已知限制（v1 没做的）

- 没有托盘图标和开机自启 —— 退出走右键菜单或关掉终端。
- 没有打包成 exe，还是 `npm start` 跑。
- 没有语音、没有屏幕感知。
- 模型是程序化几何，不能换姿势以外的东西；要换形象得改 `model.js`。
- 只支持 Windows（透明窗口 + `setIgnoreMouseEvents` 的行为在别的系统上没验证）。

## 下一步可以加

1. `electron-builder` 打包成单文件 exe，托盘菜单 + 开机自启。
2. 说话改成流式打字机（现在已经是流式，但气泡一次性替换文本，可以做逐字效果）。
3. 桌面感知：读当前窗口标题 → 主动冒一句“在写代码？要不要休息”。
4. 语音唤醒（Porcupine 或本地 whisper）。
