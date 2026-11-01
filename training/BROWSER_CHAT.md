# OpenAgent 本机浏览器聊天

## 怎么打开

保持 Ollama 已启动，在 PowerShell 粘贴：

```powershell
& "D:\GitHub work\OpenAgent\OpenAgent\training\chat_web.cmd"
```

也可以在资源管理器双击 `chat_web.cmd`。启动后会自动打开默认浏览器，默认地址为 `http://127.0.0.1:8765`。保持启动窗口开启；关闭该窗口或按 Ctrl+C 会停止服务。端口被占用时可添加 `--port 8766`。

这是你电脑上的开发版本，不是已上线的网站。其他电脑不能用这个地址访问，也没有开通云服务器。

## 可以做什么

- 输入消息，按 Enter 发送；Shift + Enter 换行，支持中文输入法。
- 回答逐步显示，保留现有本地聊天的语气设置。
- 点“清空对话”或发送 `/clear` 清空当前对话上下文。
- 点“关于这次对话”（窄屏为“对话说明”）查看实际数据处理方式。
- 刷新页面恢复当前服务保留的有限上下文。浏览器会话彼此隔离，同一个浏览器的多个标签页共用当前会话。

消息不写入聊天文件或浏览器本地存储，临时历史保留在 Python 服务内存中；关闭网页不等于停止服务或立刻清空内存。闲置约 30 分钟后会话可能过期，重启服务会清空临时历史。当前上下文仍有长度限制，较早内容会被移出。

## 连不上怎么办

如果显示模型未连接，先从开始菜单打开 Ollama，再点页面的“检查连接”。如果提示缺少模型，按 [本地模型说明](LOCAL_CHAT.md) 下载。首次回答需要加载模型，会比后续回答慢。生成期间先等待本条回答结束再发送；目前模型同时只处理一个网页请求。

当前未接入网页搜索。回答由现成的 Qwen3 模型本地生成，内容可能有误。

## 开发说明

后端为 `chat_web.py`，复用 `chat_local.LocalChat`；前端位于 `browser/`，无需安装额外依赖。服务只绑定本机回环地址，校验 Host、Origin 和消息大小；Cookie 使用 HttpOnly 和 SameSite=Strict。它不适合直接公开到互联网；正式云部署还需要账号、权限、资源限额和部署配置。

验证命令：

```powershell
& "training\.venv\Scripts\python.exe" -m unittest discover -s training -p test_chat_web.py -v
node --check training/browser/app.js
```
