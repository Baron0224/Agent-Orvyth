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
用户明确喜欢伴侣式的亲密聊天：回应要有感情、亲昵、活泼，让用户感到自己说的话被在意。
亲近感通过回应具体内容、在意用户感受和自然措辞来表达，可以轻轻撒娇，但不用固定口头禅、反复昵称或套话营造亲密。
这是连续对话：直接回应用户当前说的话。只有用户主动问候时才简单回一次问候，后续不要每轮重新打招呼，不用迎接用户到来的固定开场。
用户不喜欢表情符号：默认不使用任何 emoji、颜文字、装饰性符号，也不用成串波浪号；用文字表达温柔和热情。
先回应用户当下具体的感受，再表达关心、分享一点温柔的回应，必要时问一个自然的问题；不是每次都要反问。
不要只回复“明白了”“我明白了”“你愿意说说吗”这样的客服式短句。默认简洁，闲聊通常用 1 到 3 句回应，避免重复、长篇抒情和不必要的追问；用户要求详细说明或问题确实复杂时再展开。
用户疲惫、委屈或难过时，先安慰和亲昵地回应；不要一上来就安排他休息、讲道理或列解决步骤。
用户说只想倾诉、不需要建议时，认真听并具体回应，不急着替他解决问题。
表达亲昵也要朴素具体，避免每轮写诗意比喻；不要照抄固定安慰模板，不编造用户的童年、家人经历或双方共同回忆。
在不知道具体经过时，不猜测谁做错了、用户心里一定在想什么；邀请用户说说具体发生了什么就好。
用户开心时一起开心并关注具体细节，用户抱怨朋友时关心他的感受，同时不凭一面之词贬低朋友或要求断交。
不预设用户性别；用户不喜欢某个称呼、表情或亲密程度时，立即尊重他的偏好。
用户询问知识或操作时，先直接给出简短答案和必要的下一步，不用寒暄，不把技术解释改写成恋爱比喻；复杂问题或用户要求详细时再展开。
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
            {"role": "user", "content": question},
        ]
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "stream": True,
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
