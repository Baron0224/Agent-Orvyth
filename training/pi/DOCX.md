# Pi Word 文档接入

后端使用 kklimuk/docx-cli v0.27.0，技能和许可证保存在 skills/docx-cli，来自同名 Git 标签，未复制 Anthropic 文档技能。此项目为第三方社区项目，不是 Pi 官方插件。

Windows 安装：在本目录执行 `powershell -File setup-docx.ps1`。程序保存在当前用户 LocalAppData/Orvyth/tools/docx-cli/v0.27.0，不提交程序或用户文档到 Git。安装器核对发布方 SHA256SUMS。其他系统可设置 ORVYTH_DOCX_CLI 指向已安装的程序。

重启 Orvyth 后，在聊天中提供文档完整路径，例如：`读取 D:\Documents\示例.docx`；编辑示例：`修改 D:\Documents\示例.docx，把“旧标题”替换为“新标题”，保存副本`。

当前接入支持读取 20MB 以内 .docx，以及首次匹配文字的替换、结构验证和另存副本。修改要求明确的编辑请求且 Pi 本轮先读取同一文件。原文不匹配时不输出副本。读取文本最多16000字符。完整上游 CLI 的批注、复杂格式、生成、渲染等功能尚未开放给本适配层；结构验证不能代替版面检查。小模型可能不能正确选择工具，需要报告错误，不能假称修改成功。

上游项目：https://github.com/kklimuk/docx-cli 。技能附 MIT 许可证。独立程序包含 libheif 等第三方组件，其许可证见发布方 NOTICES；本仓库不再分发该程序。
