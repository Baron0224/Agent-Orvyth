"""Answer by retrieving a similar reviewed question from a local Q&A corpus."""

import argparse
from difflib import SequenceMatcher
import getpass
import html
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request


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
    character_score = 0.6 * sequence_score + 0.4 * overlap_score

    # Short rephrasings often preserve a technical name such as README or PyTorch.
    left_terms = set(re.findall(r"[a-z][a-z0-9_]*", left.lower()))
    right_terms = set(re.findall(r"[a-z][a-z0-9_]*", right.lower()))
    if left_terms and right_terms:
        query_term_coverage = len(left_terms & right_terms) / len(left_terms)
        character_score = max(character_score, 0.6 * character_score + 0.4 * query_term_coverage)
    return character_score


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


def conversational_fallback(question):
    greeting = question.strip().strip("，。！？!?、,. ").lower()
    if greeting in {"你好", "您好", "嗨", "哈喽", "hello", "hi", "早上好", "晚上好"}:
        return "你好呀，我在呢。今天想聊点什么？"
    if greeting in {"谢谢", "谢谢你", "多谢", "感谢"}:
        return "不用谢呀。能陪你一起把事情理清楚，我很开心。还有什么想和我聊的吗？"
    if greeting in {"再见", "拜拜", "回头见", "晚安"}:
        return "好呀，那你先去忙。之后还想聊的话，再回来找我。"

    urgent_phrases = ("伤害自己", "自杀", "不想活", "结束生命", "轻生")
    if any(phrase in question for phrase in urgent_phrases):
        return (
            "我很担心你现在的安全。请先远离可能伤害自己的物品，马上联系身边可信任的人陪着你，"
            "并联系当地急救或危机支持服务；如果有立即危险，请立刻拨打当地急救电话。"
        )

    emotional_phrases = (
        "迷茫", "孤独", "难过", "伤心", "不开心", "难受", "我不好", "不太好",
        "状态不好", "烦恼", "焦虑", "委屈", "失落", "撑不住", "压力很大",
        "心情不好", "心情不太好", "心里堵", "想哭",
    )
    if any(phrase in question for phrase in emotional_phrases):
        return "我在呢。听起来你最近被这件事困扰着，愿意跟我说说发生了什么吗？我先听你说，不急着给建议。"
    return None


def search_web(query, api_key, count=5):
    endpoint = "https://api.search.brave.com/res/v1/web/search"
    url = f"{endpoint}?{urllib.parse.urlencode({'q': query, 'count': count, 'safesearch': 'moderate'})}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": "OpenAgent-local-search/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise RuntimeError("Brave 搜索密钥无效，请检查后重试。") from None
        if error.code == 429:
            raise RuntimeError("Brave 搜索请求达到当前额度或频率限制。") from None
        raise RuntimeError(f"网页搜索失败（HTTP {error.code}）。") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("暂时无法连接 Brave 搜索，请检查网络后重试。") from None

    results = payload.get("web", {}).get("results", [])
    if not results:
        print("OpenAgent：我没有搜到合适的网页结果。你可以换个关键词再试一次。")
        return

    print("OpenAgent：我在网上找到这些页面，先把来源给你；下面是搜索摘要，不是模型核实后的结论：")
    for index, result in enumerate(results[:count], start=1):
        title = html.unescape(re.sub(r"<[^>]*>", "", result.get("title", "无标题")))
        description = html.unescape(re.sub(r"<[^>]*>", "", result.get("description", "")))
        print(f"\n{index}. {title}")
        if description:
            print(f"   摘要：{description}")
        print(f"   来源：{result.get('url', '')}")


parser = argparse.ArgumentParser(description="从本地问答语料中检索相似问题")
parser.add_argument("--corpus", default="corpus.txt", help="training 目录中的语料文件名")
parser.add_argument("--threshold", type=float, default=0.42, help="回答所需的最低相似度，范围 0 到 1")
parser.add_argument("--web", action="store_true", help="本地语料无匹配时，使用 Brave Search 搜索网页")
args = parser.parse_args()

if not 0.0 <= args.threshold <= 1.0:
    parser.error("--threshold 必须在 0 到 1 之间")

corpus_path = Path(__file__).with_name(args.corpus)
pairs = load_pairs(corpus_path)
if not pairs:
    raise ValueError(f"没有从 {corpus_path.name} 中找到相邻的用户/助手问答。")

api_key = None
if args.web:
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY") or getpass.getpass("输入 Brave Search API 密钥（输入内容不会显示）：").strip()
    if not api_key:
        raise SystemExit("没有输入 API 密钥，联网搜索未启动。")
    print("联网搜索已开启：本地没有匹配的问题会发送到 Brave Search。请勿输入密码或其他私密信息。")

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
        fallback = conversational_fallback(question)
        if fallback:
            print(f"OpenAgent（陪伴回应，未从语料检索）：{fallback}")
        elif args.web:
            try:
                search_web(question, api_key)
            except RuntimeError as error:
                print(f"OpenAgent：{error}")
        else:
            print("OpenAgent：这个问题我现在还没有把握，不想随便编给你。你愿意多说一点背景吗？我可以陪你一起找答案。")
    else:
        warm_intro = "嗯，我陪你一起看看："
        if answer.startswith(warm_intro):
            answer = answer[len(warm_intro) :].lstrip()
        print(f"OpenAgent（匹配度 {score:.2f}，参考问题：{matched_question}）：{warm_intro}{answer}")
