"""保留独立规格失败原字节，并核验源码、XML、完整快照及自有资源。"""
import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import asyncpg
from redis.asyncio import Redis

ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
RAW = Path("/tmp/m3-task9-wholespec-3f2b2095-92a9-45b5-bcf8-55b2e2eabd2c")
DEST = ROOT / "docs/superpowers/reports/task9-chain-spec-failure-evidence"
REPORT = ROOT / "docs/superpowers/reports/2026-11-02-m3-task9-chain-spec-failure.md"
RESULT = Path("/tmp/m3-task9-source-integrity-spec-result.md")
HEAD = "c45bf55e1aa5753eb1d83ad8a3eb60487b741474"
OLD = "3444cf1967f9b5c9d64fde824dd4b53333a29143"
SOURCE_SHA = "1dd2eb166f857df67ad0b513540d7ee8e12f5e47c1f74354d2832029521baf65"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def combined(mapping):
    return sha(json.dumps(sorted(mapping.items()), ensure_ascii=True,
                          separators=(",", ":")).encode())


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd)


def verify_blobs(revision, mapping):
    request = "".join(f"{revision}:{name}\n" for name in mapping).encode()
    data = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, input=request,
                          capture_output=True, check=True).stdout
    pos = 0
    for name, digest in mapping.items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert len(header) == 3 and header[1] == b"blob", name
        length = int(header[2])
        pos = end + 1
        blob = data[pos:pos + length]
        assert sha(blob) == digest and (ROOT / name).read_bytes() == blob, name
        pos += length + 1
    assert pos == len(data)


async def resources(cleanup):
    db = await asyncpg.connect(user="postgres", database="postgres",
                               host="127.0.0.1", port=55432)
    try:
        remaining = await db.fetchval(
            "SELECT count(*) FROM pg_database WHERE datname = ANY($1::text[])",
            cleanup["exact_databases"])
    finally:
        await db.close()
    redis = Redis.from_url("redis://127.0.0.1:56379/0")
    try:
        streams = await redis.exists(*cleanup["exact_streams"])
    finally:
        await redis.aclose()
    closed = {}
    for port in cleanup["ports_connect_ex"]:
        with socket.socket() as client:
            client.settimeout(1)
            closed[port] = client.connect_ex(("127.0.0.1", int(port))) != 0
    assert remaining == streams == 0 and all(closed.values())
    return {"exact_databases": len(cleanup["exact_databases"]),
            "remaining_databases": remaining,
            "exact_streams": len(cleanup["exact_streams"]),
            "remaining_streams": streams, "ports_closed": closed}


def scan(data, name, secrets):
    # 仅报告路径，不输出候选秘密；固定本地测试授权值不当作真实模型密钥。
    assert b"-----BEGIN PRIVATE KEY-----" not in data, name
    assert b"-----BEGIN RSA PRIVATE KEY-----" not in data, name
    assert not re.search(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", data), name
    for secret in secrets:
        assert secret not in data, name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-head")
    args = parser.parse_args()
    if args.verify_head:
        assert git("rev-parse", "HEAD").decode().strip() == args.verify_head
        assert git("rev-parse", "HEAD^").decode().strip() == HEAD
        assert not git("status", "--porcelain")
        assert not git("diff", HEAD, args.verify_head, "--", "python", "frontend")
        proof = json.loads((DEST / "parent-retention.json").read_bytes())
        mapping = dict(proof["preexisting_git_blobs"])
        prefix = str(DEST.relative_to(ROOT)) + "/"
        mapping.update({prefix + p: s for p, s in proof["retained_files"].items()})
        mapping[prefix + "parent-retention.json"] = sha(
            (DEST / "parent-retention.json").read_bytes())
        mapping[str(REPORT.relative_to(ROOT))] = sha(REPORT.read_bytes())
        verify_blobs(args.verify_head, mapping)
        expected = {p for p in mapping if p.startswith(prefix)} | {
            str(REPORT.relative_to(ROOT))}
        changed = {p.decode() for p in git("diff", "--name-only", "-z", HEAD,
                                          args.verify_head).split(b"\0") if p}
        assert expected == changed
        print(json.dumps({"head": args.verify_head, "parent": HEAD,
                          "changed_docs_paths": len(changed),
                          "all_git_blobs_exact": len(mapping),
                          "product_source_unchanged": True}, indent=2))
        return

    assert not DEST.exists() and not REPORT.exists()
    assert git("rev-parse", "HEAD").decode().strip() == HEAD
    assert not git("status", "--porcelain")
    primary = ROOT.with_name("eduagent")
    assert git("rev-parse", "HEAD", cwd=primary).decode().strip() == (
        "2ff803c968d64741d149e5a1ce88a823d4d32422")
    assert not git("status", "--porcelain", cwd=primary)
    manifest_bytes = (RAW / "retained-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert len(manifest["files"]) == 398
    assert combined(manifest["files"]) == manifest["payload_sha256"] == (
        "8cb8c5a30a5e3c4c15067378585a4419f0853dbc033e0b03f02e04e0116ce962")
    assert RESULT.read_bytes() == (RAW / "review-result.md").read_bytes()
    proof = json.loads((RAW / "independent-verification.json").read_bytes())
    baseline_bytes = (RAW / "full-before.json").read_bytes()
    baseline = json.loads(baseline_bytes)
    source = baseline["m3"]["source"]
    assert len(source) == 353 and combined(source) == SOURCE_SHA
    tracked = {p.decode() for p in git("ls-files", "-z", "--", "python",
                                      "frontend").split(b"\0") if p}
    assert set(source) == tracked
    assert len(proof["snapshots"]) == 34
    for name, declaration in proof["snapshots"].items():
        data = (RAW / name).read_bytes()
        expected = declaration if isinstance(declaration, str) else declaration["sha256"]
        assert sha(data) == expected and data == baseline_bytes, name
    assert (RAW / "final-source-after.json").read_bytes() == baseline_bytes
    preexisting = dict(source)
    for base, tip, count in ((OLD + "^", OLD, 206), (OLD, HEAD, 246)):
        names = [p.decode() for p in git("diff", "--name-only", "-z", base,
                                         tip).split(b"\0") if p]
        assert len(names) == count
        for name in names:
            preexisting[name] = sha((ROOT / name).read_bytes())
    verify_blobs(HEAD, preexisting)
    assert len(preexisting) == 802
    xml = {}
    for name, declaration in proof["suites"].items():
        data = (RAW / name).read_bytes()
        assert sha(data) == declaration["sha256"]
        cases = list(ET.fromstring(data).iter("testcase"))
        failures = sum(c.find("failure") is not None for c in cases)
        errors = sum(c.find("error") is not None for c in cases)
        skips = sum(c.find("skipped") is not None for c in cases)
        actual = {"tests": len(cases), "passed": len(cases)-failures-errors-skips,
                  "failures": failures, "errors": errors, "skips": skips}
        assert actual == {k: declaration[k] for k in actual}, name
        xml[name] = actual
    assert len(xml) == 16
    cleanup = asyncio.run(resources(json.loads(
        (RAW / "cleanup-verification.json").read_bytes())))
    secrets = [value.encode() for key, value in os.environ.items()
               if len(value) >= 12 and re.search(
                   r"(?:API_KEY|API_TOKEN|SIGNING_SECRET|ASSIGNMENT_SECRET)$", key)]
    zip_count = 0
    for name, digest in manifest["files"].items():
        path = Path(name)
        assert not path.is_absolute() and ".." not in path.parts
        data = (RAW / path).read_bytes()
        assert sha(data) == digest, name
        scan(data, name, secrets)
        if path.suffix == ".zip":
            zip_count += 1
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert archive.testzip() is None
                for item in archive.infolist():
                    if not item.is_dir():
                        scan(archive.read(item), name + ":" + item.filename, secrets)
    assert zip_count == 70
    DEST.mkdir()
    for name in manifest["files"]:
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RAW / name, target)
    shutil.copyfile(RAW / "retained-manifest.json", DEST / "retained-manifest.json")
    shutil.copyfile(Path(__file__), DEST / "parent-retain.py")
    REPORT.write_bytes(RESULT.read_bytes())
    retained = {str(p.relative_to(DEST)): sha(p.read_bytes())
                for p in DEST.rglob("*") if p.is_file()}
    result = {
        "verified_at": datetime.now(UTC).isoformat(),
        "role": "parent provenance/byte-exact retention; not SPEC or CODE acceptance",
        "head": HEAD, "source_count": 353, "source_sha256": SOURCE_SHA,
        "original_payload_files": 398,
        "original_manifest_sha256": sha(manifest_bytes),
        "original_payload_sha256": manifest["payload_sha256"],
        "retained_files": retained, "preexisting_git_blobs": preexisting,
        "xml": xml, "complete_equal_snapshots": 35,
        "exact_resource_check": cleanup, "trace_zip_crc_checked": zip_count,
        "secret_scan": {"known_environment_values_checked": len(secrets),
                        "private_key_and_provider_key_patterns_checked": True},
        "valid_failure": "S1-R/P2: invalid referenced Canary leaves Active Shadow consumed",
        "invalid_attempts_retained": ["relations-api 0 collection",
                                     "chain-metadata 2 FK fixture failures"],
        "parent_visual_check": ["referenced poison desktop left",
                                "referenced poison mobile left"],
        "model_requests": 0, "release_eligible": False,
    }
    (DEST / "parent-retention.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, digest in manifest["files"].items():
        assert sha((DEST / name).read_bytes()) == digest
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("retained_files", "preexisting_git_blobs", "xml")},
                     indent=2))


if __name__ == "__main__":
    main()
