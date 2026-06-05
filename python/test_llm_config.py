"""快速测试 .env 中配置的 LLM 是否可用。"""

import asyncio
import sys
import os

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保在 python 目录下运行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    from config.settings import settings
    from llm import get_llm, Message

    print("=" * 50)
    print("LLM 配置检测")
    print("=" * 50)
    print(f"  Provider: {settings.configured_llm_provider}")
    print(f"  Model:    {settings.configured_llm_model}")
    print(f"  Base URL: {settings.openai_base_url}")
    key = settings.openai_api_key
    print(f"  API Key:  {key[:10]}...{key[-4:]}")
    print()

    llm = get_llm()
    print(f"  LLM 类型: {llm.__class__.__name__}")
    print(f"  Runtime:  {llm.runtime_info()}")
    print()

    print("发送测试请求...")
    print("-" * 50)

    messages = [
        Message(role="system", content="你是一个英语教学助手。请用中文简短回复。"),
        Message(role="user", content="请用一句话解释什么是现在完成时？"),
    ]

    try:
        response = await llm.chat(messages, temperature=0.7, max_tokens=200)
        print(f"  [OK] 成功")
        print(f"  回复: {response.content}")
        print(f"  模型: {response.model}")
        print(f"  用量: {response.usage}")
        print(f"  结束: {response.finish_reason}")
    except Exception as e:
        print(f"  [FAIL] 失败")
        print(f"  错误类型: {type(e).__name__}")
        print(f"  错误信息: {e}")

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
