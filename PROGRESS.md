# OpenAgent 进度记录

> 用途：记录项目做到哪一步，方便下次继续。每次有进展后更新“当前进度”和“下一步”。

## 项目目标

和朋友一起学习并制作自己的 AI 智能体。当前方向是先学习从随机参数开始训练小型模型，不调用其他模型 API；逐步理解训练、数据和应用之间的关系。

## 已完成

- 创建 GitHub 仓库 `Baron0224/OpenAgent`。
- 将 Dify 源码放入现有 OpenAgent 仓库，并推送到 GitHub。
- 在本机通过 Docker Desktop 启动 Dify，浏览器可以打开 `http://localhost`。
- 创建 Dify Chatflow 应用 `OpenAgent1.0`。尚未配置模型供应商，因此它目前不能独立回答问题。
- 在仓库新增 `training/` 目录和 `corpus.txt` 示例语料。
- 创建 `training/train.py`：字符统计入门示例，从语料文件读取文本并生成字符序列。
- 创建 `training/train_nn.py`：用 PyTorch 编写的小型 GRU 字符语言模型，从随机权重开始训练，不加载预训练模型、不调用外部 API。
- 建立 `training/.venv` 虚拟环境，使用 Python 3.13 和 PyTorch 2.14.1 CUDA 13.0；确认 CUDA 可用，识别到 NVIDIA GeForce RTX 4060 Laptop GPU。
- 成功训练一次，损失值从约 4.187 降至接近 0，并生成权重文件 `training/tiny_model.pt`。最初语料约 91 个字符，模型主要是记住样例，生成能力很有限。
- 扩充 `training/corpus.txt`，加入用户自己写的 OpenAgent目标和语气描述；使用 RTX 4060 Laptop GPU 重新训练成功，训练损失从 4.661 降到 0.001，生成样例出现了语料中的内容，显示小模型在记忆短语料。
- 已将训练脚本更新为按文本顺序划分 80% 训练集和 20% 验证集，并保存词表和上下文长度。实际运行结果：step 0 train loss 4.332 / val loss 4.556；step 300 train loss 0.001 / val loss 5.996。训练损失下降、验证损失上升，说明模型在极短语料上明显过拟合。
- 上述项目进度与训练文件已推送到 GitHub；最近一次核对时本地 `main` 与 `origin/main` 同步。

## 当前进度

已完成从零训练小型 GRU 字符模型及训练集/验证集对比。当前语料约 178 个字符，验证集仅 36 个字符，损失趋势可作过拟合演示但统计结论不稳定。模型不是通用聊天大模型，也尚未接入 Dify。

## 下一步

1. 运行更新后的 `training/train_nn.py`，观察 train loss 和 val loss 是否有明显差距。
2. 继续扩充 `training/corpus.txt`，围绕 OpenAgent 的目标和对话示例准备自己编写或明确允许训练的文本；避免个人隐私和未经许可的材料。
3. 学习重新加载模型并做简单评估，再讨论如何把训练出的模型接入 Dify。

## 每次继续时

先读本文件的“当前进度”和“下一步”，确认实际文件及 GitHub 状态，再从下一步继续。完成后更新本文件并提交推送。

