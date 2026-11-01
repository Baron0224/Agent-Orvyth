# OpenAgent 本地模型聊天

现在也可以使用 [浏览器聊天页面](BROWSER_CHAT.md)，启动 `chat_web.cmd` 即可。下面保留终端聊天入口的说明。

这个入口使用本机 Ollama 和现成的 Qwen3 4B 指令模型生成回答，可回答语料文件中没有的问题。它与 `train_nn.py`、`train_qa.py` 的从零训练实验是两个入口。当前未接入网页搜索，也未发布网站或打包桌面安装程序。

## 第一次准备

1. 安装 [Ollama Windows 版](https://ollama.com/download/windows)。
2. 在 PowerShell 运行 `ollama pull qwen3:4b-instruct`，下载约 2.5GB 的本地模型。模型文件不要提交进 Git。模型是 Apache 2.0 许可，详见[模型页面](https://ollama.com/library/qwen3:4b-instruct)。
3. 确认 Ollama 已启动，双击本目录的 `chat_local.cmd` 开始聊天。

本机已选择把模型存放到 `D:\OpenAgentModels\ollama`，通过用户环境变量 `OLLAMA_MODELS` 配置。Ollama 云端功能由 `OLLAMA_NO_CLOUD=1` 关闭。模型下载和软件更新需要网络；本地推理调用的是 `127.0.0.1:11434`，不需要第三方云端模型密钥。

## PowerShell 启动命令

```powershell
& "D:\GitHub work\OpenAgent\OpenAgent\training\.venv\Scripts\python.exe" -X utf8 "D:\GitHub work\OpenAgent\OpenAgent\training\chat_local.py"
```

输入 `exit` 退出，`/clear` 清空当前对话，`/privacy` 查看本聊天脚本的数据处理说明。常见的直接询问聊天记录的问题也会返回程序固定说明，不依赖模型猜测。对话历史只留在当前程序内存里，退出后不由脚本保存；这不代表其他软件或操作系统没有日志。程序限制历史长度以控制资源占用，较早的内容会被移出上下文。首次回答需要加载模型，通常会比后续回答慢。输出可能出错，不代表事实已核实。

闲聊使用用户选择的热情、亲昵、有恋爱氛围的风格，通常 2 至 6 句，直接回应具体内容，不反复打招呼；默认不用 emoji、颜文字或装饰性符号，用自然措辞表达关心。用户只想倾诉时先听，不主动列建议，不编造用户经历或共同回忆。用户可以直接要求调整称呼或亲密程度。知识和操作问题按内容需要认真解释，仍可要求详细回答。修改提示词后，需要退出并重新运行聊天程序才能生效。

如果提示无法连接，先从开始菜单打开 Ollama。如果提示缺少模型，运行上面的 `ollama pull` 命令。用 `ollama ps` 可以查看模型是否运行在 GPU 上。

## 后续两种交付方式

先用这套本地生成能力验证聊天体验。最终桌面客户端和网站版可连接统一部署的模型服务，让用户不必自行安装 Ollama；当前仅在开发电脑上验证，尚未部署云端。服务器上的模型不能直接公开裸接口，网站需要独立实现访问控制和资源限制；当前服务仅供本机使用。
