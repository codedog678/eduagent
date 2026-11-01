import ipaddress
import json
import os
from pathlib import Path
import re
import socket


def pytest_configure(config):
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
