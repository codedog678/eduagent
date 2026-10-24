"""检查主链路配置；仅显式 --live 时发送可能计费的连通性请求。"""

import argparse
import asyncio
import json
import sys
import os

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保在 python 目录下运行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main(live: bool = False) -> int:
    from core.llm_service import get_llm_service

    print("LLM 配置检测")
    try:
        llm = get_llm_service()
    except ValueError:
        print("[FAIL] 配置无效，请检查 LLM_PROVIDER、对应 API Key 和模型参数。")
        return 2
    print(f"  Runtime:  {llm.runtime_info()}")
    if not live:
        print("仅检查本地配置，未发送请求。使用 --live 可测试标准 API（可能计费）。")
        return 0
    if not llm.runtime_info()["llm_enabled"]:
        print("[FAIL] 未配置可用的远程模型。")
        return 1

    print("发送连通性请求（可能计费）...")

    try:
        # 可见正文或合法工具调用均能证明连通；截断和无效响应仍视为失败。
        response = await llm.tool_turn(
            [{"role": "system", "content": "你是英语教学助手，用中文简短回复。"},
             {"role": "user", "content": "请用一句话解释现在完成时。"}],
            [{"type": "function", "function": {
                "name": "get_knowledge_context", "description": "查询知识点",
                "parameters": {"type": "object", "properties": {}}}}],
            max_tokens=800,
        )
        if response.stop_reason in {"tool_calls", "tool_use"}:
            calls = response.tool_calls
            valid = bool(calls) and len({call.id for call in calls}) == len(calls) and all(
                call.id and call.name == "get_knowledge_context"
                and json.loads(call.arguments) == {} for call in calls
            )
            if not valid:
                print("[FAIL] 模型返回了无效的工具调用。")
                return 1
            print("[OK] 鉴权与原生工具协议正常，模型请求 get_knowledge_context。")
            print(f"用量: {response.usage}")
            return 0
        if response.stop_reason not in {"stop", "end_turn"}:
            print(f"[FAIL] 请求未得到完整回复：{response.stop_reason}")
            return 1
        if not response.content.strip():
            print("[FAIL] 模型未返回可见正文。")
            return 1
        print(f"[OK] {response.content}")
        print(f"用量: {response.usage}")
        return 0
    except Exception as exc:
        # 不回显异常原文，避免凭据或请求内部信息泄露。
        print(f"[FAIL] 错误类型: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="发送可能计费的标准 API 请求")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(live=args.live)))
