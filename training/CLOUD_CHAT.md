# Orvyth 云端聊天

日常云端聊天已并入 8775。在原来的 Edge 日常账户打开 http://127.0.0.1:8775/ ，进入「设置 → 聊天引擎」选择云端或自动。也可用旧启动命令打开正式入口：

```powershell
& "D:\Codex\Orvyth\training\chat_cloud.cmd"
```

8775 读取启动进程的 `DEEPSEEK_API_KEY` 环境变量或已经保存的加密密钥。检测不到可用密钥时，网页会提示「云端未配置」。不要把密钥发到聊天、写入代码或上传 GitHub。
以前保存的密钥位于 `%LOCALAPPDATA%/Orvyth/credentials/deepseek.dpapi`，用 Windows DPAPI（系统提供的当前用户加密服务）保护。
关闭终端结束服务。若要忘记保存的密钥，执行后输入 `y` 确认：

```powershell
& "D:\Codex\Orvyth\training\chat_cloud.cmd" --forget-key
```

只删除本程序的固定密钥文件，不删除聊天资料或环境变量；正在运行的服务仍可能持有旧密钥，下次启动才生效。若环境变量仍设置，启动仍会优先使用它。
Windows加密依据：[Microsoft CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)。

旧 8776 不再是日常入口。它独立的 `Orvyth/cloud/browser.sqlite3`、档案和会话保留备查，不会自动迁进 8775。

聊天使用 DeepSeek 官方 `deepseek-flash`，显式关闭思考模式，保留共用口吻、称呼和有限记忆。
问题、选中历史、选中的长期档案和本轮网页摘要会发给DeepSeek；文件工具仍使用本机Pi与Qwen，需要本机Ollama。
文件工具的回答保存在云端版聊天后，后续问答可能把该聊天中选取的文件内容发送给DeepSeek。不要在云端聊天读取不愿外发的资料。
配置密钥只代表可以尝试，API是否可用须以真实请求为准；模型口吻和答案质量也需要实际体验。

官方API按使用计费。本轮开发未发起付费请求。
默认每次最多生成512个token（模型计量文字的单位），可用 `ORVYTH_CLOUD_MAX_TOKENS` 设置16到2048的整数。
达到上限、断流、401认证失败、402余额不足、429限流会显示错误；不重试、不自动切回本地，不保存失败或截断的问答。
停止接收会关闭连接，但已经生成的内容可能仍由服务商计费。
成功回答的官方usage计数随完成事件返回，并保存在 `/api/session` 的对应助手消息 `usage` 字段，包含提供商、模型及返回的token计数；不保存密钥。
此计数不是账单，费用以DeepSeek控制台为准；未调用模型的本机固定回复没有usage。

官方文档：[接口](https://api-docs.deepseek.com/api/create-chat-completion/)、[关闭思考](https://api-docs.deepseek.com/guides/thinking_mode/)、[错误码](https://api-docs.deepseek.com/quick_start/error_codes/)。
