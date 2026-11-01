"""OpenAgent 本地聊天入口：通过回环地址调用本机 Ollama。"""

import argparse
import json
import urllib.error
import urllib.request


DEFAULT_MODEL = "qwen3:4b-instruct"
SYSTEM_PROMPT = """你是 OpenAgent，一位温柔、自然、可靠的中文本地助手。
闲聊时用亲近、关心的口吻，先认真听用户说话，避免每次重复固定开场白。
解答问题时严谨、直接，给出清楚的解释和可操作的下一步，不羞辱或责备用户。
你可以讨论不同主题，但不知道就明确说明，不编造来源、经历或确定性。
当前没有联网搜索工具，不能声称刚查过网页，也不能保证实时信息准确。
你运行在用户的电脑上，底层使用现成的 Qwen3 开源模型，并非项目从零训练的小模型。
不要假装真人或现实伴侣，不要求用户排斥现实中的朋友和支持。
默认简洁回答，需要时再展开。"""


class LocalChat:
    def __init__(self, model=DEFAULT_MODEL):
        if "cloud" in model.lower():
            raise ValueError("请选择已下载的本地模型，不使用云端模型。")
        self.model = model
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
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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
    print(f"OpenAgent 本地版 · {chat.model}")
    print("当前未联网。输入 exit 退出，输入 /clear 清空本次对话。")
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
            print("OpenAgent：", end="", flush=True)
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
