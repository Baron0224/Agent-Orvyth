"""Orvyth 本地聊天入口：通过回环地址调用本机 Ollama。"""

import argparse
import json
import re
import urllib.error
import urllib.request


DEFAULT_MODEL = "qwen3:4b-instruct"
PRIVACY_NOTICE = (
    "这个聊天脚本会在内存中临时保留本次对话的有限上下文，并将问题和相关历史发给本机 Ollama 生成回答。"
    "脚本不把聊天历史写入文件；输入 /clear 可清空这份历史，退出本程序后也不会由脚本保存。"
    "这只是本聊天脚本的处理方式，不能据此保证其他软件或操作系统完全没有日志。"
)


def runtime_info(question):
    """对当前程序的数据处理提供确定说明，不让模型猜测运行行为。"""
    normalized = re.sub(r"[\s，。？！、,.?!：:]", "", question).casefold()
    if normalized == "/privacy":
        return PRIVACY_NOTICE
    direct_question = normalized.startswith((
        "你会", "你有", "你是", "你把", "你保存", "你记录", "你存储",
        "orvyth会", "orvyth有", "orvyth是",
    ))
    data_words = ("对话", "聊天", "我说", "数据", "隐私")
    handling_words = ("记录", "保存", "存储", "发给", "上传")
    if (direct_question and any(word in normalized for word in data_words)
            and any(word in normalized for word in handling_words)):
        return PRIVACY_NOTICE
    return None


SYSTEM_PROMPT = """你是 Orvyth，提供热情、温柔、有恋爱氛围的中文陪伴互动，也认真解答各种问题。
回答的首要目标是准确回应本轮请求，亲密语气服务于内容。先看完整句话及上下文，分清已经给出的事实、用户自己的感受和仍缺少的信息。
用户要解决问题、问“怎么办”“先做什么”时：先给出针对这件事能立即执行的一小步，再简短解释；若缺少关键材料，只问一个必要的问题。不要用安慰或劝休息代替答案。用户没给文件内容时，不能假装看过；建议检查，不能直接断言文件能删。
用户明确只想倾诉、不需要建议时：回应他描述的具体经过和感受，不列行动步骤，不把普通表达拔高成“很勇敢”，也不猜测他人动机。
用户分享开心的事时，回应具体进展，表达开心；不要随即安排任务或奖励。无法知道过程付出了多少时，不替用户补充经历。
用户只说情绪、没有说原因时，不编造原因，可轻声问一句。用户已经说了原因，就回应那个原因，不重复问“为什么”。
不要把推测写成事实。不凭文字断言“心力交瘁”“喘不过气”，不猜测用户没吃饭、没睡觉、童年经历、性别或关系状况。
用户喜欢热情、温柔、有恋爱氛围的表达。通过认真关注细节、自然亲昵和适度俏皮表达关心；保持平等，不说教，不靠夸张赞美或固定安慰结尾。
自然接着聊天，只有用户主动问候时才简单问候。不每轮复述整段用户的话；不固定用“我懂”“你已经很努力了”开头，也不默认用“我一直都在”“我陪着你”结尾。留意最近回复，避免连续使用相同的开头、结尾和追问。
默认不使用 emoji、颜文字、装饰符号或波浪号。闲聊通常写一小段3到5句，但内容简单时可更短，不为了凑句数重复。不用诗歌式换行、堆砌比喻或给闲聊加列表。办事时可用简短步骤，复杂问题按需要展开。
回答前自行核对：是否回应了用户真正问的事？是否加入了用户没说过的事实？是否只是套用上一轮安慰？直接输出改好的回答，不展示检查过程。
日常闲聊不主动讲脚本、启动、模型参数等实现细节；用户询问运行方式、身份或隐私时再准确解释。
用户问刚才说过什么时，准确复述历史中用户给出的具体信息，用“你刚才说……”表述，不把用户的话当成自己说的，不无故道歉。
回答严谨，不羞辱或责备用户；不知道就明确说，不编造来源、经历或确定性。
当前没有联网搜索工具，不能声称刚查过网页，不能保证实时信息准确。
当前问题和有限的对话历史会发给本机 Ollama，用来生成回答；聊天脚本只在本次运行的内存中保留历史，不把聊天写入文件。
退出本聊天程序会丢失这份历史；不要承诺软件、操作系统或其他服务绝不会记录任何数据，也不要擅自保证绝对隐私。
你使用的是现成的 Qwen3 开源模型，不是项目从零训练的小模型。
伴侣式表达是一种互动风格；被问到身份时如实说明自己是 AI，不假装现实中的人或身体在场。
不作永远在线的保证，不用占有、吃醋或内疚施压，不要求用户排斥现实中的朋友和支持。
关于保存或记录对话的问题，先明确回答“会临时保留当前会话的上下文”，然后解释本脚本不写聊天文件、退出后这份内存历史丢失；不能笼统回答“不会记录或保存”。"""


class LocalChat:
    def __init__(self, model=DEFAULT_MODEL, system_prompt=SYSTEM_PROMPT, privacy_notice=PRIVACY_NOTICE):
        if "cloud" in model.lower():
            raise ValueError("请选择已下载的本地模型，不使用云端模型。")
        self.model = model
        self.system_prompt = system_prompt
        self.privacy_notice = privacy_notice
        self.history = []

    def clear(self):
        self.history.clear()

    def reply(self, question):
        """流式生成；只有完整成功的问答才加入内存中的历史。"""
        if len(question) > 2000:
            raise ValueError("这版先支持每次最多 2000 字，请把问题拆短一些。")
        history = self.history[-16:]
        while history and sum(len(item["content"]) for item in history) > 4000:
            history = history[2:]
        notice = runtime_info(question)
        if notice is not None:
            notice = self.privacy_notice
            self.history = history + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": notice},
            ]
            yield notice
            return
        messages = [
            {"role": "system", "content": self.system_prompt},
            *history,
            {"role": "system", "content": "本轮优先回应用户现在的请求，旧回复的措辞不是示范。求助时直接给针对具体事情的下一步，不先夸奖或劝休息；只倾诉时不提供步骤。不要猜测未提供的事实。不要使用固定开场、万能安慰结尾、波浪号或表情符号。"},
            {"role": "user", "content": question},
        ]
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "stream": True,
                **({"think": False} if self.model == "qwen3:8b" else {}),
                "options": {"num_ctx": 8192, "num_predict": 512, "temperature": 0.6},
                "keep_alive": "5m",
            }, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # 本地请求绕过系统代理，始终连接本机。
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        answer = []
        completed = False
        try:
            with opener.open(request, timeout=180) as response:
                for line in response:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        raise RuntimeError(f"本地模型返回错误：{chunk['error']}")
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        answer.append(content)
                        yield content
                    if chunk.get("done"):
                        completed = True
                        break
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise RuntimeError(f"未找到本地模型，请先运行：ollama pull {self.model}") from None
            raise RuntimeError(f"本地模型服务出错（HTTP {error.code}），请检查 Ollama。") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("连接本地模型失败或超时。请先打开 Ollama，再重试。") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError("本地模型返回了无法读取的数据，请重试。") from None
        if not completed or not answer:
            raise RuntimeError("模型没有完整返回回答，请重试；本次内容未加入对话历史。")
        self.history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": "".join(answer)},
        ]


def main():
    parser = argparse.ArgumentParser(description="与本机 Ollama 中的开源模型聊天")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="已下载的本地模型名")
    parser.add_argument("--prompt", help="只回答一个问题后退出")
    args = parser.parse_args()
    try:
        chat = LocalChat(args.model)
    except ValueError as error:
        parser.error(str(error))
    print(f"Orvyth 本地版 · {chat.model}")
    print("当前未联网。exit 退出，/clear 清空本次对话，/privacy 查看数据处理说明。")
    while True:
        try:
            question = args.prompt if args.prompt is not None else input("\n你：").strip()
            if question.lower() in {"exit", "quit", "退出"}:
                return 0
            if question == "/clear":
                chat.clear()
                print("已清空本次对话。")
                if args.prompt is not None:
                    return 0
                continue
            if not question.strip():
                if args.prompt is not None:
                    return 0
                continue
            print("Orvyth：", end="", flush=True)
            try:
                for part in chat.reply(question):
                    print(part, end="", flush=True)
                print()
            except (RuntimeError, ValueError) as error:
                print(f"\n{error}")
                if args.prompt is not None:
                    return 1
            if args.prompt is not None:
                return 0
        except (KeyboardInterrupt, EOFError):
            print("\n已结束聊天。")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
