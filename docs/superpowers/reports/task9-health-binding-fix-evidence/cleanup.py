"""Check recorded own databases and remove only explicitly owned UUID streams."""
import asyncio
import json
from pathlib import Path
import re
import socket

import asyncpg
from redis.asyncio import Redis

OWN = Path(__file__).parent


async def main():
    recorded = []
    for path in OWN.glob("*cleanup.log"):
        tokens = path.read_text().split()
        assert len(tokens) == 2 and tokens[0] == "dropped"
        assert tokens[1].startswith("m3_t9_hfix_")
        recorded.append(tokens[1])
    connection = await asyncpg.connect(host="127.0.0.1", port=55432, user="postgres", database="postgres")
    databases = await connection.fetch("SELECT datname FROM pg_database WHERE datname = ANY($1::text[])", recorded)
    await connection.close()
    redis = Redis.from_url("redis://127.0.0.1:56379/0")
    streams = sorted({json.loads(line)["stream"] for line in (OWN / "redis-owned.jsonl").read_text().splitlines()})
    for stream in streams:
        assert re.fullmatch(r"test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*", stream)
    existing = sum([await redis.exists(stream) for stream in streams])
    if streams:
        await redis.delete(*streams)
    remaining = sum([await redis.exists(stream) for stream in streams])
    await redis.aclose()
    ports = {}
    for port in (33520, 33521):
        with socket.socket() as connection:
            ports[str(port)] = connection.connect_ex(("127.0.0.1", port)) != 0
    result = {"recorded_databases": recorded, "remaining_databases": [r["datname"] for r in databases],
              "own_streams": streams, "existing_streams_before": existing, "remaining_streams": remaining,
              "own_ports_closed": ports}
    (OWN / "cleanup-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    assert not databases and not remaining and all(ports.values())
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in result.items()}, indent=2))


asyncio.run(main())
