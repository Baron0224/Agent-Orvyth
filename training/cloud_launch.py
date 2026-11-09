"""Hidden key input, optional user-scoped encrypted storage, child environment only."""
import argparse
from cloud_credentials import load_key, save_key, forget_key
import getpass
import os
from pathlib import Path
import subprocess
import sys
import warnings


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--forget-key', action='store_true')
    args = parser.parse_args(argv)
    if args.forget_key:
        try:
            if not sys.stdin.isatty() or input('仅删除Orvyth本机保存的DeepSeek密钥？输入 y 确认：').strip().lower() != 'y':
                print('已取消，保存的密钥未更改。')
                return 0
            forget_key()
        except (EOFError, KeyboardInterrupt):
            print('\n已取消，保存的密钥未更改。')
            return 0
        except (OSError, ValueError, KeyError):
            print('无法删除保存的密钥，请检查本机文件权限。')
            return 1
        print('已忘记本机保存的密钥；环境变量不受影响，运行中的服务仍可能持有旧密钥，下次启动生效。')
        return 0
    key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if not key:
        try:
            key = load_key()
        except (OSError, ValueError, KeyError):
            print('已保存密钥无法读取，原文件未删除。可重新输入，或使用 --forget-key 明确忘记。')
    if not key:
        if not sys.stdin.isatty():
            print('请在本机终端运行 training/chat_cloud.cmd，隐藏输入密钥。')
            return 1
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                key = getpass.getpass('DeepSeek API 密钥（输入不显示，仅本次运行使用）：').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n已取消启动。')
            return 1
        except (getpass.GetPassWarning, OSError):
            print('此终端无法隐藏输入，已取消；请使用本机 PowerShell。')
            return 1
        if key:
            try:
                choice = input('是否加密保存到本机，便于同Windows账户下次免输？[y/N，c取消启动]：').strip().lower()
            except (EOFError, KeyboardInterrupt):
                print('\n已取消启动，未保存密钥。')
                return 1
            if choice == 'c':
                print('已取消启动，未保存密钥。')
                return 1
            if choice == 'y':
                try:
                    save_key(key)
                    print('已加密保存到本机。同Windows账户程序仍可能读取它，不是绝对安全。')
                except (OSError, ValueError, KeyError):
                    print('加密或保存失败，原保存文件未主动删除；本次仍可使用，下次可能需要重新输入。')
    if not key:
        print('没有输入密钥，未启动云端服务。')
        return 1
    command = [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('chat_web.py')),
               '--port', '8776', '--model', 'deepseek-cloud:deepseek-flash',
               '--tool-model', 'qwen3:8b', '--open']
    print('云端聊天将向DeepSeek发送本轮问题、选中的聊天上下文和长期档案；尚未验证API。')
    try:
        return subprocess.call(command, env={**os.environ, 'DEEPSEEK_API_KEY': key})
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())
