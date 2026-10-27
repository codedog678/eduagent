"""无网络后端回归入口；本地 .env 的模型/embedding 凭据不能进入测试。"""

import os
from pathlib import Path
import socket
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MINIMAX_API_KEY",
                "DEEPSEEK_API_KEY", "MEMORY_EMBEDDING_API_KEY", "SILICONFLOW_API_KEY"):
        os.environ[key] = ""
    os.environ["LLM_PROVIDER"] = "template"
    # 保留离线规则摘录，测试可自行覆盖配置；关闭自动后台任务。
    os.environ["MEMORY_EXTRACTION_ENABLED"] = "true"
    os.environ["MEMORY_WORKER_ENABLED"] = "false"

    def deny_network(*args, **kwargs):
        raise AssertionError("offline test runner forbids network connections")

    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    import pytest
    return pytest.main(sys.argv[1:] or ["tests", "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
