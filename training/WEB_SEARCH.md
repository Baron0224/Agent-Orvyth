# Orvyth 网页搜索

## 浏览器版新闻查询

`chat_web.py` 的新闻问题会读取 [BBC World 公开 RSS](https://feeds.bbci.co.uk/news/world/rss.xml)，无需搜索密钥。支持例如“说出2026.11.4的新闻”，按这台电脑时区下的文章发布日期筛选，再由本机模型翻译标题。发布日不一定等于事件发生日，只覆盖该源近期部分国际新闻；RSS没有保留的旧日期会明确返回未查到，不会改用其他日期。此方式只获取标题与时间，不能保证模型翻译完全正确，也不是完整网页搜索。

以下是旧命令行检索器的 Brave 配置，和浏览器版分开使用。

检索器默认只查本地 `corpus.txt`。加上 `--web` 后，本地没有匹配的问题会通过 Brave Search 网页搜索接口查找，并显示网页标题、摘要和来源链接。当前版本展示搜索结果，不会让小模型总结或保证搜索摘要正确。

## 设置

1. 在 [Brave Search API 控制台](https://api-dashboard.search.brave.com/) 注册或登录，并创建 Web Search API 密钥。此功能使用网页搜索接口，不使用 Brave 的 AI Answers 或其他 AI 模型接口。
2. 在 PowerShell 运行 `answer_qa_retrieval.py --web`。
3. 程序提示时，在 PowerShell 里输入 API 密钥并按回车。输入过程不会显示密钥；程序只在当前运行期间使用它，不会写入语料或 Git 仓库。

联网模式会把没有匹配到本地问答的问题发送给 Brave Search。不要输入密码、访问令牌、个人隐私或其他不希望发送给搜索服务的内容。搜索 API 的额度和价格以 [Brave 官方页面](https://brave.com/search/api/) 为准。

## PowerShell 启动命令

```powershell
& "D:\GitHub work\OpenAgent\OpenAgent\training\.venv\Scripts\python.exe" "D:\GitHub work\OpenAgent\OpenAgent\training\answer_qa_retrieval.py" --web
```

没有 `--web` 时，程序保持离线，只检索本地语料。
