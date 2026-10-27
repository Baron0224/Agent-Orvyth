from copy import deepcopy
from pathlib import Path
import random

import torch
from torch import nn

# 有 NVIDIA CUDA 时使用显卡，否则使用 CPU。
device = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(42)

# 将相邻的用户问题和助手回答合并成完整对话段落，让训练样本包含
# “用户问题\n助手回答”的上下文；其他普通文本仍单独作为一段。
text_path = Path(__file__).with_name("corpus.txt")
lines = [
    line.strip()
    for line in text_path.read_text(encoding="utf-8-sig").splitlines()
    if line.strip()
]
segments = []
pending_user = None
for line in lines:
    if line.startswith("用户："):
        if pending_user is not None:
            segments.append(pending_user)
        pending_user = line
    elif line.startswith("助手：") and pending_user is not None:
        segments.append(pending_user + "\n" + line)
        pending_user = None
    else:
        if pending_user is not None:
            segments.append(pending_user)
            pending_user = None
        segments.append(line)
if pending_user is not None:
    segments.append(pending_user)

if len(segments) < 5:
    raise ValueError("语料至少需要 5 段非空文本，才能划分训练集和验证集。")

# 按段落随机划分，避免把文件末尾某一种话题单独当成验证集。
rng = random.Random(42)
rng.shuffle(segments)
val_count = max(1, round(len(segments) * 0.2))
val_segments = segments[:val_count]
train_segments = segments[val_count:]

vocab = sorted(set("".join(segments)))
to_id = {char: i for i, char in enumerate(vocab)}
from_id = {i: char for char, i in to_id.items()}
context_size = 12

# 每段单独建立预测样本，不让样本跨越段落边界。
def make_examples(selected_segments):
    inputs = []
    targets = []
    for segment in selected_segments:
        ids = [to_id[char] for char in segment]
        for i in range(len(ids) - context_size):
            inputs.append(ids[i:i + context_size])
            targets.append(ids[i + context_size])

    if not inputs:
        raise ValueError("训练集或验证集太短。请让每段文字超过 12 个字符，并增加语料段落。")

    return (
        torch.tensor(inputs, dtype=torch.long, device=device),
        torch.tensor(targets, dtype=torch.long, device=device),
    )

train_inputs, train_targets = make_examples(train_segments)
val_inputs, val_targets = make_examples(val_segments)

class TinyLanguageModel(nn.Module):
    def __init__(self, vocab_size, hidden_size=64):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.rnn = nn.GRU(hidden_size, hidden_size, batch_first=True)
        self.output = nn.Linear(hidden_size, vocab_size)

    def forward(self, x):
        x = self.embedding(x)
        x, _ = self.rnn(x)
        return self.output(x[:, -1, :])

hidden_size = 64
model = TinyLanguageModel(len(vocab), hidden_size=hidden_size).to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)
loss_fn = nn.CrossEntropyLoss()

@torch.no_grad()
def evaluate_loss(inputs, targets):
    model.eval()
    value = loss_fn(model(inputs), targets).item()
    model.train()
    return value

# 训练最多 500 步；验证集连续 5 次没有改善时提前停止。
max_steps = 500
evaluate_every = 25
patience_limit = 5
best_val_loss = float("inf")
best_step = 0
best_state = None
steps_without_improvement = 0

for step in range(max_steps + 1):
    model.train()
    logits = model(train_inputs)
    loss = loss_fn(logits, train_targets)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    if step % evaluate_every == 0 or step == max_steps:
        train_loss = evaluate_loss(train_inputs, train_targets)
        val_loss = evaluate_loss(val_inputs, val_targets)
        print(f"step {step:3d} | train loss {train_loss:.3f} | val loss {val_loss:.3f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_step = step
            best_state = deepcopy(model.state_dict())
            steps_without_improvement = 0
        else:
            steps_without_improvement += 1
            if steps_without_improvement >= patience_limit:
                print("验证损失连续多次没有改善，提前停止训练。")
                break

# 保存验证集表现最好的参数，而不是最后一步的参数。
model.load_state_dict(best_state)

@torch.no_grad()
def generate(start, length=100, temperature=0.8, top_k=5):
    model.eval()
    unknown_chars = sorted(set(start) - set(to_id))
    if unknown_chars:
        raise ValueError(f"提示词里有语料未出现的字符：{''.join(unknown_chars)}。请换成语料中已有的文字。")

    result = start
    for _ in range(length):
        context = result[-context_size:]
        x = torch.tensor([[to_id[char] for char in context]], dtype=torch.long, device=device)
        logits = model(x)[0] / temperature
        if top_k is not None and top_k < logits.numel():
            cutoff = torch.topk(logits, top_k).values[-1]
            logits[logits < cutoff] = float("-inf")
        probabilities = torch.softmax(logits, dim=0)
        next_id = torch.multinomial(probabilities, num_samples=1).item()
        result += from_id[next_id]
    return result

weights_path = Path(__file__).with_name("tiny_model.pt")
torch.save({
    "model": model.state_dict(),
    "vocab": vocab,
    "context_size": context_size,
    "hidden_size": hidden_size,
    "best_step": best_step,
    "best_val_loss": best_val_loss,
}, weights_path)

print(f"\n训练完成，设备：{device}")
print(f"训练段落：{len(train_segments)}，验证段落：{len(val_segments)}")
print(f"训练样本：{len(train_targets)}，验证样本：{len(val_targets)}")
print(f"最佳步骤：{best_step}，最佳验证损失：{best_val_loss:.3f}")
print(f"最佳权重已保存到：{weights_path.name}")
print("固定提示生成检查（字符级模型可能仍会生成不连贯文本）：")
prompts = [
    "用户：我总是被手机分心，学习计划做不完。\n助手：",
    "用户：我现在不需要建议，只想把事情说出来。\n助手：",
    "用户：为什么模型会重复句子？\n助手：",
]
for prompt in prompts:
    print(f"\n提示：{prompt}")
    print(f"续写：{generate(prompt)}")
