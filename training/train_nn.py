from pathlib import Path
import torch
from torch import nn

# Use the GPU when CUDA is available; otherwise fall back to CPU.
device = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(42)

# Load our own training text. This model starts with random weights.
text_path = Path(__file__).with_name("corpus.txt")
text = text_path.read_text(encoding="utf-8-sig").replace("\n", " ")
if len(text) < 20:
    raise ValueError("Please add at least 20 characters to corpus.txt")

vocab = sorted(set(text))
to_id = {char: i for i, char in enumerate(vocab)}
from_id = {i: char for char, i in to_id.items()}
data = torch.tensor([to_id[c] for c in text], dtype=torch.long, device=device)

# Make short examples: read 12 characters and predict the next one.
context_size = 12
inputs = torch.stack([data[i:i + context_size] for i in range(len(data) - context_size)])
targets = data[context_size:]

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

# Train from scratch on the supplied corpus.
for step in range(301):
    logits = model(inputs)
    loss = loss_fn(logits, targets)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    if step % 100 == 0:
        print(f"step {step:3d} | loss {loss.item():.3f}")

@torch.no_grad()
def generate(start="人工智能", length=100):
    model.eval()
    result = start
    for _ in range(length):
        context = result[-context_size:]
        # If a character is not in the training vocabulary, use a known character.
        context = "".join(c if c in to_id else vocab[0] for c in context)
        x = torch.tensor([[to_id[c] for c in context]], dtype=torch.long, device=device)
        probs = torch.softmax(model(x)[0], dim=0)
        next_id = torch.multinomial(probs, num_samples=1).item()
        result += from_id[next_id]
    return result

# Save the trained weights locally for later experiments.
weights_path = Path(__file__).with_name("tiny_model.pt")
torch.save({"model": model.state_dict(), "vocab": vocab}, weights_path)
print(f"\nTraining complete on {device}. Saved weights to: {weights_path.name}")
print("Generated sample:")
print(generate())
