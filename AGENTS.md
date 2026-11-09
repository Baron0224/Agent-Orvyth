# AGENTS.md

> 仓库根规则。`training/` 下是 Orvyth 自有代码；`api/`、`web/`、`dify-agent/` 等是保留的上游 Dify 源码。
> 仓库维护者正在学习编程，**下面「变更讲解规则」是本仓库的硬性要求，优先级高于简洁偏好**。

## 变更讲解规则（强制）

每次修改代码后，**先输出「变更说明」，再报交付结果**。不要只写「已修复」「已优化」「已接入」——没有变更说明视为任务未完成。用中文，用日常语言，不堆术语。

固定五段：

### 1. 改了什么

- `完整/相对路径:起止行` —— 这个文件在项目里负责什么（一句话。禁止「相关逻辑」「部分内容」「若干调整」这类空话）
- 具体改动：`原来做 X` → `现在做 Y`

### 2. 为什么这么改

- 触发原因：哪个 bug、哪个需求、哪种失败场景
- 另一条路是什么、为什么不走（一句话即可）

### 3. 你能自己动手改的

- 想调整 <某个具体行为>，改 `路径:行号` 里的 `<具体变量名 / 常量 / 字符串>`
- 一处都没有就写「无」

### 4. 用到的工具 / 插件

- 名称：它是什么、这次为什么用它、不用它行不行
- 只列本次真正用到的；没有写「无」

### 5. 一句话总结

> 外行也能听懂的一句话，说明这次改动解决了什么问题。禁止「提升了健壮性」「优化了架构」这类零信息量表述。

## 写学习日志

输出变更说明之后，把同样内容**追加**到 `training/LEARNING_LOG.md`（append-only，不改旧条目）：

```markdown
## [YYYY-MM-DD] <一句话标题>
- 改了：`路径:行号` —— 文件职责；`X` → `Y`
- 因为：触发原因
- 我能改：`路径:行号` 的 `变量名`
- 工具：名称 —— 用途
```

## 学习友好约定

- 提到文件时永远写**完整相对路径 + 行号**，不要只写文件名。
- 第一次出现的专有名词（上下文窗口、向量检索、检索增强、embedding 等）用一句话解释。
- 不确定就直说「我不确定」，不要用模糊表述掩盖；不能验证的结论标为「未验证」。
- 区分清楚：**已改本地 / 已重启生效 / 已推送 GitHub / 已上线**，不要合并成「已完成」。

---

## 继承自上游 Dify 的说明

Dify is an open-source platform for building LLM applications, agentic workflows, and RAG pipelines. This monorepo contains the backend API (`api/`), frontend application (`web/`), deployment assets (`docker/`), standalone agent backend (`dify-agent/`), CLI (`cli/`), and end-to-end suite (`e2e/`). Follow the nearest scoped `AGENTS.md` for the files being changed. Apply its guidance within the user's requested scope; explicit user instructions take precedence over workflow defaults.

## Repository Gotchas

- Run backend commands through `uv run --project api <command>`.
- Backend integration tests are CI-only and are not expected to run locally.
- Keep `docker/.env.example` limited to variables required for a default Docker Compose deployment to start. Put optional and provider-specific settings in the matching `docker/envs/*.env.example` file; `docker/.env` overrides those service-specific env files.

## Orvyth 固定产品身份与口吻

`training/PERSONA.md` 是实际运行时共用的身份与表达来源，终端、网页和新旧聊天都应遵守。维护时保留私人AI秘书身份、热恋期般宠溺简洁的表达、不自我贬低与不会不编的要求；事实、权限和执行结果仍须如实说明，不把这套语气当作伪称人类或隐藏服务失败的许可。未经用户新指示，不另加相冲突的人格提示。
