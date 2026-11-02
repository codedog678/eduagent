import ipaddress
import json
import os
from pathlib import Path
import re
import socket


def pytest_configure(config):
    from redis.asyncio import Redis
    execute = Redis.execute_command
    created_keys = set()

    async def ledger(self, *args, **kwargs):
        command = str(args[0]).upper()
        verb = command.split()[0]
        assert command not in {"FLUSHALL", "FLUSHDB"}, "no flush"
        keys = []
        if command in {"DEL", "UNLINK"}:
            keys = [str(k) for k in args[1:]]
            assert all(
                re.fullmatch(r"(?:test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*|eduagent:test:failover:[0-9a-f]{32})", k)
                and (not k.startswith("eduagent:") or k in created_keys)
                for k in keys)
        elif verb in {"XADD", "XREAD", "XREADGROUP", "XGROUP", "XACK", "XCLAIM", "XAUTOCLAIM"}:
            if command == "XGROUP":
                keys = [str(args[2])]
            elif verb == "XGROUP":
                keys = [str(args[1])]
            elif command not in {"XREAD", "XREADGROUP"}:
                keys = [str(args[1])]
            if verb in {"XGROUP", "XADD"}:
                created_keys.update(keys)
        with (Path(os.environ["REVIEW_OWN"]) / "redis-command-ledger.jsonl").open("a") as file:
            file.write(json.dumps({"invocation": os.environ["EVIDENCE_RUN"], "command": command,
                                   "exact_keys": keys, "args_count": len(args)}) + "\n")
        return await execute(self, *args, **kwargs)

    Redis.execute_command = ledger
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple):
            try:
                allowed = ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                allowed = address[0] == "localhost"
            assert allowed, "SPEC prohibits non-loopback connections"
        return original(sock, address)

    socket.socket.connect = connect
    from core.distributed.broker import RedisStreamBroker
    original_reset = RedisStreamBroker.reset_for_tests

    async def own_reset(self):
        assert re.fullmatch(r"test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*", self.stream)
        with (Path(os.environ["REVIEW_OWN"]) / "redis-owned.jsonl").open("a") as file:
            file.write(json.dumps({"stream": self.stream}) + "\n")
        return await original_reset(self)

    RedisStreamBroker.reset_for_tests = own_reset
