"""Train a small character-level question-to-answer GRU from random weights."""

from copy import deepcopy
from pathlib import Path
import random

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_sequence


device = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(42)
random.seed(42)

corpus_path = Path(__file__).with_name("corpus.txt")
lines = [
    line.strip()
    for line in corpus_path.read_text(encoding="utf-8-sig").splitlines()
    if line.strip()
]

# Build supervised question/answer pairs from adjacent corpus lines.
pairs = []
pending_question = None
for line in lines:
    if line.startswith("用户："):
        pending_question = line.removeprefix("用户：").strip()
    elif line.startswith("助手：") and pending_question is not None:
        answer = line.removeprefix("助手：").strip()
        if pending_question and answer:
            pairs.append((pending_question, answer))
        pending_question = None
    else:
        pending_question = None

if len(pairs) < 10:
    raise ValueError(f"只找到 {len(pairs)} 组相邻问答；请检查 corpus.txt 的用户/助手格式。")

random.shuffle(pairs)
val_count = max(1, round(len(pairs) * 0.2))
val_pairs = pairs[:val_count]
train_pairs = pairs[val_count:]

PAD_ID, BOS_ID, EOS_ID = 0, 1, 2
vocab = sorted(set("".join(question + answer for question, answer in pairs)))
to_id = {char: index + 3 for index, char in enumerate(vocab)}
from_id = {index: char for char, index in to_id.items()}
vocab_size = len(vocab) + 3


def encode_batch(selected_pairs):
    questions = []
    decoder_inputs = []
    targets = []
    question_lengths = []

    for question, answer in selected_pairs:
        question_ids = [to_id[char] for char in question] + [EOS_ID]
        answer_ids = [to_id[char] for char in answer]
        questions.append(torch.tensor(question_ids, dtype=torch.long))
        decoder_inputs.append(torch.tensor([BOS_ID] + answer_ids, dtype=torch.long))
        targets.append(torch.tensor(answer_ids + [EOS_ID], dtype=torch.long))
        question_lengths.append(len(question_ids))

    return (
        pad_sequence(questions, batch_first=True, padding_value=PAD_ID).to(device),
        torch.tensor(question_lengths, dtype=torch.long),
        pad_sequence(decoder_inputs, batch_first=True, padding_value=PAD_ID).to(device),
        pad_sequence(targets, batch_first=True, padding_value=PAD_ID).to(device),
    )


train_questions, train_lengths, train_decoder_inputs, train_targets = encode_batch(train_pairs)
val_questions, val_lengths, val_decoder_inputs, val_targets = encode_batch(val_pairs)


class QuestionAnswerModel(nn.Module):
    def __init__(self, size, hidden_size=128):
        super().__init__()
        self.embedding = nn.Embedding(size, hidden_size, padding_idx=PAD_ID)
        self.encoder = nn.GRU(hidden_size, hidden_size, batch_first=True)
        self.decoder = nn.GRU(hidden_size, hidden_size, batch_first=True)
        self.output = nn.Linear(hidden_size, size)

    def encode(self, questions, lengths):
        embedded = self.embedding(questions)
        packed = pack_padded_sequence(
            embedded, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        _, hidden = self.encoder(packed)
        return hidden

    def forward(self, questions, lengths, decoder_inputs):
        hidden = self.encode(questions, lengths)
        decoded, _ = self.decoder(self.embedding(decoder_inputs), hidden)
        return self.output(decoded)


hidden_size = 128
model = QuestionAnswerModel(vocab_size, hidden_size=hidden_size).to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
loss_fn = nn.CrossEntropyLoss(ignore_index=PAD_ID)


@torch.no_grad()
def evaluate_loss(questions, lengths, decoder_inputs, targets):
    model.eval()
    logits = model(questions, lengths, decoder_inputs)
    loss = loss_fn(logits.reshape(-1, vocab_size), targets.reshape(-1)).item()
    model.train()
    return loss


max_steps = 500
evaluate_every = 25
patience_limit = 5
best_val_loss = float("inf")
best_step = 0
best_state = None
steps_without_improvement = 0

for step in range(max_steps + 1):
    model.train()
    logits = model(train_questions, train_lengths, train_decoder_inputs)
    loss = loss_fn(logits.reshape(-1, vocab_size), train_targets.reshape(-1))
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()

    if step % evaluate_every == 0 or step == max_steps:
        train_loss = evaluate_loss(
            train_questions, train_lengths, train_decoder_inputs, train_targets
        )
        val_loss = evaluate_loss(val_questions, val_lengths, val_decoder_inputs, val_targets)
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

model.load_state_dict(best_state)
model.eval()

weights_path = Path(__file__).with_name("tiny_qa_model.pt")
torch.save(
    {
        "model": model.state_dict(),
        "vocab": vocab,
        "context_size": None,
        "hidden_size": hidden_size,
        "best_step": best_step,
        "best_val_loss": best_val_loss,
    },
    weights_path,
)


@torch.no_grad()
def generate_answer(question, max_length=160, temperature=0.8, top_k=5):
    unknown_chars = sorted(set(question) - set(to_id))
    if unknown_chars:
        raise ValueError(f"问题里有语料未出现的字符：{''.join(unknown_chars)}")

    model.eval()
    question_ids = [to_id[char] for char in question] + [EOS_ID]
    question_tensor = torch.tensor([question_ids], dtype=torch.long, device=device)
    lengths = torch.tensor([len(question_ids)], dtype=torch.long)
    hidden = model.encode(question_tensor, lengths)
    token = torch.tensor([[BOS_ID]], dtype=torch.long, device=device)
    answer = []

    for _ in range(max_length):
        decoded, hidden = model.decoder(model.embedding(token), hidden)
        logits = model.output(decoded[0, -1]) / temperature
        logits[PAD_ID] = float("-inf")
        logits[BOS_ID] = float("-inf")
        if top_k is not None and top_k < vocab_size:
            cutoff = torch.topk(logits, top_k).values[-1]
            logits[logits < cutoff] = float("-inf")
        token_id = torch.multinomial(torch.softmax(logits, dim=0), num_samples=1).item()
        if token_id == EOS_ID:
            break
        answer.append(from_id[token_id])
        token = torch.tensor([[token_id]], dtype=torch.long, device=device)

    return "".join(answer)


print(f"\n问答模型训练完成，设备：{device}")
print(f"问答组：训练 {len(train_pairs)}，验证 {len(val_pairs)}")
print(f"最佳步骤：{best_step}，最佳验证损失：{best_val_loss:.3f}")
print(f"最佳权重已保存到：{weights_path.name}")
print("验证集问题生成检查（字符级模型仍可能答非所问）：")
for question, _ in val_pairs[:3]:
    print(f"\n用户：{question}")
    print(f"助手：{generate_answer(question)}")
