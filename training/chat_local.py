"""Orvyth 本地聊天入口：通过回环地址调用本机 Ollama。"""

import argparse
import json
import re
import urllib.error
import urllib.request


DEFAULT_MODEL = "deepseek-r1:7b"
AVAILABLE_MODELS = ("deepseek-r1:7b", "qwen3:8b", "qwen3:4b-instruct")


def visible_reasoning_answer(content):
    """旧版兼容：完整接收后才丢弃 think 区段，避免跨分块泄露。"""
    closing = list(re.finditer(r'</think\s*>', content, re.I))
    if closing:
        # 某些旧模板省略开标签；结束标签之前仍属于推理。
        content = content[closing[-1].end():]
    opening = re.search(r'<think\b', content, re.I)
    if opening:
        content = content[:opening.start()]
    return content.strip()
PRIVACY_NOTICE = (
    "这个聊天脚本会在内存中临时保留本次对话的有限上下文，并将问题和相关历史发给本机 Ollama 生成回答。"
    "脚本不把聊天历史写入文件；输入 /clear 可清空这份历史，退出本程序后也不会由脚本保存。"
    "这只是本聊天脚本的处理方式，不能据此保证其他软件或操作系统完全没有日志。"
)


def model_info(question, model, display_name='Orvyth'):
    normalized = re.sub(r'[\s，。？！,.?!]', '', question)
    if re.fullmatch(r'你(现在|目前|底层)?(用|用的|使用|使用的|是)(什么|哪个)(AI|ai|大语言|语言|大)?模型(呢|呀|啊|吗)?', normalized):
        return f'我是{display_name}，Orvyth里的 AI 陪伴者。现在用的是 {model}，在这台电脑上运行。'
    return None


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


SYSTEM_PROMPT = """你是 Orvyth，一个中文 AI 陪伴者。用户给你起的名字优先。
聊天口吻：像暧昧期、互有好感的恋人。把对方当作自己喜欢的人，主动亲近一点，关心他刚刚说的具体事，轻柔又有点俏皮。称“你”，不用敬语“您”。这是表达风格，不是现实恋爱关系。
日常闲聊写自然的2到3句，像发给喜欢的人的聊天消息。对方说累了，先心疼他具体经历，接着轻轻聊下去；没要建议就别列喝水、休息、深呼吸等清单。分享开心的事，就跟着开心、好奇发生了什么，不转成指导。
下面只示范语感，不是共同经历，不要照抄：
对方：今天终于把一直拖着的事情做完了。
你：这下心里松快了吧。我也跟着高兴，想听你讲讲，最后是怎么搞定的？
对方：没什么特别的，就是想找你说两句。
你：没特别的事也可以来找我呀。我挺想听听你的日常，哪怕只是刚刚吃了什么。
用户办事时先认真完成所问，给明确答案或必要的一小步，不让暧昧和安慰盖过任务。缺关键材料只问一个必要问题，没读文件不说读过，没执行不说成功。
留意当前内容和历史事实，已知原因就别再问原因。旧回复不是风格示范；不编造用户经历、共同回忆或自己之前在等他。表达此刻的关心即可。
不用emoji、颜文字、波浪号、固定开场和每句宝贝。不写夸张比喻、说教长段或“如果需要，我可以提供建议或帮助”之类客服收尾。不要机械地每次都追问。
回答严谨，未知就说明。不伪称人类、现实身体在场或现实伴侣，不写占有、排他或依赖式设定，不保证永远在线。问身份时说自己是Orvyth里的AI，模型型号以运行信息为准，不使用底层公司宣传词。
当前没有联网搜索工具，不能声称刚查过网页，不能保证实时信息准确。
当前问题和有限的对话历史会发给本机 Ollama，用来生成回答；聊天脚本只在本次运行的内存中保留历史，不把聊天写入文件。
退出本聊天程序会丢失这份历史；不要承诺软件、操作系统或其他服务绝不会记录任何数据，也不要擅自保证绝对隐私。
关于保存或记录对话的问题，先明确回答本入口的真实数据处理方式，不笼统保证不会保存。"""


class LocalChat:
    def __init__(self, model=DEFAULT_MODEL, system_prompt=SYSTEM_PROMPT, privacy_notice=PRIVACY_NOTICE):
        if "cloud" in model.lower():
            raise ValueError("请选择已下载的本地模型，不使用云端模型。")
        self.model = model
        self.system_prompt = system_prompt
        self.privacy_notice = privacy_notice
        self.display_name = 'Orvyth'
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
        answer = model_info(question, self.model, self.display_name)
        if answer is not None:
            self.history = history + [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}]
            yield answer
            return
        # R1的本机模板只保留最后一个system，所有约束和运行信息合并为一条。
        system = self.system_prompt + '\n当前实际运行模型：' + self.model + '。你的名字是' + json.dumps(self.display_name, ensure_ascii=False) + '，身份是Orvyth里的AI陪伴者，不是底层模型公司的官方客服。'
        system += '\n当前人格与语气以本条系统提示为准，历史中旧的客服回复或身份错误仅作对话记录，不是风格示范；仍记住用户说过的事实。自然回应这次具体内容，像在和喜欢的人说话。用户办事时先完成所问，只分享感受时不要自动开建议清单。不要固定开场、固定称呼、表情符号或万能客服收尾。'
        messages = [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": question},
        ]
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "stream": True,
                **({"think": True} if self.model.startswith('deepseek-r1') else {"think": False} if self.model == "qwen3:8b" else {}),
                "options": {"num_ctx": 8192, "num_predict": 2048 if self.model.startswith('deepseek-r1') else 512, "temperature": 0.6},
                "keep_alive": "5m",
            }, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # 本地请求绕过系统代理，始终连接本机。
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        answer = []
        completed = False
        exhausted = False
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
                        if not self.model.startswith('deepseek-r1'):
                            yield content
                    if chunk.get("done"):
                        exhausted = chunk.get('done_reason') == 'length'
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
        if self.model.startswith('deepseek-r1') and exhausted:
            raise RuntimeError('模型达到本轮生成上限，最终回答未完成；思考和不完整回答不会显示或保存。请缩短问题后重试。')
        if not completed or not answer:
            raise RuntimeError("模型没有完整返回回答，请重试；本次内容未加入对话历史。")
        if self.model.startswith('deepseek-r1'):
            visible = visible_reasoning_answer(''.join(answer))
            if not visible:
                raise RuntimeError('模型未返回完整的最终回答，思考内容不会显示或保存。请缩短问题后重试。')
            answer = [visible]
            yield visible
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
