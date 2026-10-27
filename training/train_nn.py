from pathlib import Path
import torch
from torch import nn

# 有 NVIDIA CUDA 时使用显卡，否则使用 CPU。
device = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(42)

# 读取自己的语料；模型参数从随机值开始，不加载预训练模型。
text_path = Path(__file__).with_name("corpus.txt")
text = text_path.read_text(encoding="utf-8-sig").replace("\n", " ")
if len(text) < 80:
    raise ValueError("语料至少需要 80 个字符，才能划分训练集和验证集。")

vocab = sorted(set(text))
to_id = {char: i for i, char in enumerate(vocab)}
from_id = {i: char for char, i in to_id.items()}
data = torch.tensor([to_id[c] for c in text], dtype=torch.long, device=device)

# 按文本顺序切分：前 80% 用于训练，最后 20% 用于验证。
# 验证集的输入可以看到分界点之前的上下文，但验证目标不会参与训练。
context_size = 12
split_at = int(len(data) * 0.8)
train_data = data[:split_at]
val_data = data[split_at - context_size:]

if len(train_data) <= context_size or len(val_data) <= context_size:
    raise ValueError("语料太短，无法生成训练和验证样本。请扩充 corpus.txt。")

train_inputs = torch.stack([
    train_data[i:i + context_size]
    for i in range(len(train_data) - context_size)
])
train_targets = train_data[context_size:]
val_inputs = torch.stack([
    val_data[i:i + context_size]
    for i in range(len(val_data) - context_size)
])
val_targets = val_data[context_size:]

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

model = TinyLanguageModel(len(vocab)).to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)
loss_fn = nn.CrossEntropyLoss()

@torch.no_grad()
def evaluate_loss(inputs, targets):
    model.eval()
    result = loss_fn(model(inputs), targets).item()
    model.train()
    return result

# 从随机权重开始训练，并定期比较训练损失与验证损失。
for step in range(301):
    model.train()
    logits = model(train_inputs)
    loss = loss_fn(logits, train_targets)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    if step % 100 == 0:
        train_loss = evaluate_loss(train_inputs, train_targets)
        val_loss = evaluate_loss(val_inputs, val_targets)
        print(f"step {step:3d} | train loss {train_loss:.3f} | val loss {val_loss:.3f}")

@torch.no_grad()
def generate(start="人工智能", length=100):
    model.eval()
    result = start
    for _ in range(length):
        context = result[-context_size:]
        context = "".join(c if c in to_id else vocab[0] for c in context)
        x = torch.tensor([[to_id[c] for c in context]], dtype=torch.long, device=device)
        probs = torch.softmax(model(x)[0], dim=0)
        next_id = torch.multinomial(probs, num_samples=1).item()
        result += from_id[next_id]
    return result

weights_path = Path(__file__).with_name("tiny_model.pt")
torch.save({
    "model": model.state_dict(),
    "vocab": vocab,
    "context_size": context_size,
}, weights_path)

print(f"\n训练完成，设备：{device}，训练字符：{len(train_data)}，验证字符：{len(val_targets)}")
print(f"权重已保存到：{weights_path.name}")
print("生成示例：")
print(generate())
