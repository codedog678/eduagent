import ipaddress
import json
import os
from pathlib import Path
import socket


def pytest_configure(config):
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple):
            host = address[0]
            try:
                loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                loopback = host == "localhost"
            if not loopback:
                raise AssertionError("review prohibits non-loopback network connections")
        return original(sock, address)

    socket.socket.connect = connect
    from core.distributed.broker import RedisStreamBroker
    reset = RedisStreamBroker.reset_for_tests

    async def own_reset(self):
        import re
        assert re.fullmatch(r"test:(?:runs|experts):[0-9a-f]{32}", self.stream), "not an own test stream"
        path = Path(os.environ["REVIEW_OWN"]) / "redis-owned.jsonl"
        with path.open("a") as file:
            file.write(json.dumps({"stream": self.stream, "operation": "reset_for_tests"}) + "\n")
        return await reset(self)

    RedisStreamBroker.reset_for_tests = own_reset
