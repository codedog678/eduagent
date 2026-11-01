import asyncio
import json
from pathlib import Path
import re
from redis.asyncio import Redis

OWN = Path(__file__).parent


async def main():
    streams = {json.loads(line)["stream"] for line in (OWN / "redis-owned.jsonl").read_text().splitlines()}
    refused = set(re.findall(r"'(test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*)'", (OWN / "full.log").read_text()))
    streams |= refused
    # V1 stopped its fixture's cleanup at the runs stream. These siblings share
    # the same fixture UUID and are explicitly derived from configured_runtime.
    for stream in refused:
        if stream.startswith("test:schema:runs:"):
            suffix = stream.split(":")[-1]
            streams.update({
                f"test:schema:rehearsal:{suffix}",
                f"test:schema:experts:{suffix}",
                f"test:schema:runs:{suffix}:policy-deployments",
            })
        if stream.endswith(":rehearsal"):
            streams.add(stream.removesuffix(":rehearsal") + ":control")
    assert all(re.fullmatch(r"test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*", stream) for stream in streams)
    redis = Redis.from_url("redis://127.0.0.1:56379/0", decode_responses=True)
    existed = [stream for stream in sorted(streams) if await redis.exists(stream)]
    if existed:
        await redis.delete(*existed)
    remains = [stream for stream in sorted(streams) if await redis.exists(stream)]
    await redis.aclose()
    (OWN / "redis-cleanup.json").write_text(json.dumps({
        "scope": "only exact UUID streams from this review log, plus documented v1 fixture siblings",
        "enumerated": sorted(streams), "existed_and_deleted": existed, "remaining": remains,
        "flush_or_shared_scan": False,
    }, indent=2) + "\n")
    assert not remains
    print(f"own streams enumerated={len(streams)} deleted={len(existed)} remaining={len(remains)}")


asyncio.run(main())
