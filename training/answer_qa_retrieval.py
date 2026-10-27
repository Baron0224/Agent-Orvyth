"""Answer by retrieving a similar reviewed question from a local Q&A corpus."""

import argparse
from difflib import SequenceMatcher
from pathlib import Path


def normalize(text):
    return "".join(char.lower() for char in text if char.isalnum())


def bigrams(text):
    normalized = normalize(text)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def similarity(left, right):
    left_normalized = normalize(left)
    right_normalized = normalize(right)
    if not left_normalized or not right_normalized:
        return 0.0
    sequence_score = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    left_bigrams = bigrams(left)
    right_bigrams = bigrams(right)
    union = left_bigrams | right_bigrams
    overlap_score = len(left_bigrams & right_bigrams) / len(union) if union else 0.0
    return 0.6 * sequence_score + 0.4 * overlap_score


def load_pairs(path):
    lines = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
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
    return pairs


def emotional_fallback(question):
    urgent_phrases = ("伤害自己", "自杀", "不想活", "结束生命", "轻生")
    if any(phrase in question for phrase in urgent_phrases):
        return (
            "我很担心你现在的安全。请先远离可能伤害自己的物品，马上联系身边可信任的人陪着你，"
            "并联系当地急救或危机支持服务；如果有立即危险，请立刻拨打当地急救电话。"
        )

    emotional_phrases = (
        "迷茫", "孤独", "难过", "伤心", "烦恼", "焦虑", "委屈", "失落", "撑不住",
        "压力很大", "心情不好", "心里堵", "想哭",
    )
    if any(phrase in question for phrase in emotional_phrases):
        return "听起来你最近被这件事困扰着。愿意多说一点发生了什么吗？我先听你说，不急着给建议。"
    return None


parser = argparse.ArgumentParser(description="从本地问答语料中检索相似问题")
parser.add_argument("--corpus", default="corpus_project.txt", help="training 目录中的语料文件名")
parser.add_argument("--threshold", type=float, default=0.42, help="回答所需的最低相似度，范围 0 到 1")
args = parser.parse_args()

if not 0.0 <= args.threshold <= 1.0:
    parser.error("--threshold 必须在 0 到 1 之间")

corpus_path = Path(__file__).with_name(args.corpus)
pairs = load_pairs(corpus_path)
if not pairs:
    raise ValueError(f"没有从 {corpus_path.name} 中找到相邻的用户/助手问答。")

print(f"已载入 {len(pairs)} 组本地问答。输入 exit 退出。")
while True:
    question = input("\n你：").strip()
    if question.lower() in {"exit", "quit", "退出"}:
        break
    if not question:
        continue

    matched_question, answer = max(pairs, key=lambda pair: similarity(question, pair[0]))
    score = similarity(question, matched_question)
    if score < args.threshold:
        fallback = emotional_fallback(question)
        if fallback:
            print(f"OpenAgent（陪伴回应，未从语料检索）：{fallback}")
        else:
            print("OpenAgent：语料里没有找到足够相似的问题，我不确定答案。你可以补充细节，或把这组问答加入语料。")
    else:
        print(f"OpenAgent（匹配度 {score:.2f}，参考问题：{matched_question}）：{answer}")
