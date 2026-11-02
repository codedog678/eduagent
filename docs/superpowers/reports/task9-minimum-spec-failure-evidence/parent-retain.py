"""保留不足样本规格反例原字节，独立核验provenance；不替代产品验收。"""
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
from dotenv import dotenv_values

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
RAW = Path("/tmp/m3-task9-wholespec-7116c864-8783-4351-92c2-550bf3427d3e")
DEST = ROOT / "docs/superpowers/reports/task9-minimum-spec-failure-evidence"
REPORT = ROOT / "docs/superpowers/reports/2026-11-02-m3-task9-minimum-spec-failure.md"
HEAD = "ed42d33a187115825a8a94fb45ae8b4652cf4c11"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def combined(mapping):
    return sha(json.dumps(sorted(mapping.items()), ensure_ascii=True,
                          separators=(",", ":")).encode())


def git(*args, root=ROOT, **kwargs):
    return subprocess.check_output(["git", *args], cwd=root, **kwargs)


def blobs(revision, mapping):
    data = git("cat-file", "--batch",
               input="".join(f"{revision}:{p}\n" for p in mapping).encode())
    pos = 0
    for name, expected in mapping.items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert len(header) == 3 and header[1] == b"blob", name
        size = int(header[2])
        pos = end+1
        assert sha(data[pos:pos+size]) == expected, name
        pos += size+1
    assert pos == len(data)


def metadata(path):
    entries = []
    if path.exists():
        for entry in [path, *sorted(path.rglob("*"))]:
            s = entry.lstat()
            entries.append((str(entry.relative_to(path)), s.st_mode, s.st_size, s.st_mtime_ns, s.st_ino))
    return dict(entries=len(entries), sha256=sha(json.dumps(entries).encode()))


async def resources():
    cleanup = json.loads((RAW / "resource-before-shutdown.json").read_bytes())["postgres"]
    shared = cleanup["shared_service_preserved"]
    names = list(cleanup["declared_owned"].values())
    db = await asyncpg.connect(user="postgres", database="postgres", host="127.0.0.1", port=shared["port"])
    try:
        remaining = await db.fetchval("SELECT count(*) FROM pg_database WHERE datname = ANY($1::text[])", names)
        data_dir = await db.fetchval("SHOW data_directory")
    finally:
        await db.close()
    assert remaining == 0 and Path(data_dir).resolve() == Path(shared["data_dir"]).resolve()
    assert int((Path(data_dir) / "postmaster.pid").read_text().splitlines()[0]) == shared["pid"]
    closed = {}
    for port in (58479, 38730, 38731):
        with socket.socket() as sock:
            sock.settimeout(1)
            closed[str(port)] = sock.connect_ex(("127.0.0.1", port)) != 0
    assert all(closed.values())
    return dict(exact_databases=len(names), remaining_exact_databases=remaining,
                ports_closed=closed, shared_pg_preserved=True,
                redis="own nonpersistent instance stopped; no live key-query claim")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-head")
    args = parser.parse_args()
    if args.verify_head:
        tip = args.verify_head
        assert git("rev-parse", "HEAD").decode().strip() == tip
        assert git("rev-parse", "HEAD^").decode().strip() == HEAD
        assert not git("status", "--porcelain")
        proof = json.loads((DEST / "parent-retention.json").read_bytes())
        mapping = dict(proof["preexisting_git_blobs"])
        prefix = str(DEST.relative_to(ROOT)) + "/"
        mapping.update({prefix+p: h for p, h in proof["retained_files"].items()})
        mapping[prefix+"parent-retention.json"] = sha((DEST / "parent-retention.json").read_bytes())
        mapping[str(REPORT.relative_to(ROOT))] = sha(REPORT.read_bytes())
        blobs(tip, mapping)
        changed = {p.decode() for p in git("diff", "--name-only", "-z", HEAD, tip).split(b"\0") if p}
        assert changed == {p for p in mapping if p.startswith(prefix)} | {str(REPORT.relative_to(ROOT))}
        assert not git("diff", HEAD, tip, "--", "python", "frontend", "tools")
        print(json.dumps(dict(head=tip, parent=HEAD, changed_docs_paths=len(changed),
                              all_git_blobs_exact=len(mapping), product_unchanged=True), indent=2))
        return
    assert not DEST.exists() and not REPORT.exists()
    assert git("rev-parse", "HEAD").decode().strip() == HEAD
    assert not git("status", "--porcelain")
    mb = (RAW / "manifest.json").read_bytes()
    manifest = json.loads(mb)
    assert len(manifest["files"]) == 466
    assert combined(manifest["files"]) == manifest["payload_sha256"] == (
        "69900312b69b41ebd5694890112f0eef180cf634d3d81c6eca5a7dd0036e41a6")
    report = Path("/tmp/m3-task9-complete-chain-spec-result.md").read_bytes()
    assert report == (RAW / "review-result.md").read_bytes()
    assert sha(report) == manifest["report_sha256"]
    initial = (RAW / "initial-snapshot.json").read_bytes()
    state = json.loads(initial)
    source = state["m3"]["source"]
    assert len(source) == 354 and combined(source) == manifest["source_sha256"]
    preexisting = state["m3"]["tracked"]
    assert len(preexisting) == 3374
    for name, digest in preexisting.items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    blobs(HEAD, preexisting)
    for name, snapshot in state.items():
        root = ROOT if name == "m3" else ROOT.with_name("eduagent")
        assert git("rev-parse", "HEAD", root=root).decode().strip() == snapshot["head"]
        assert not git("status", "--porcelain", root=root)
        for path, digest in snapshot["tracked"].items():
            assert sha((root / path).read_bytes()) == digest, path
        index = Path(git("rev-parse", "--git-path", "index", root=root).decode().strip())
        if not index.is_absolute():
            index = root / index
        assert sha(index.read_bytes()) == snapshot["index_sha256"]
        assert index.stat().st_mtime_ns == snapshot["index_mtime_ns"]
        for key, relative in (("venv", ".venv"), ("vite", "frontend/node_modules/.vite"),
                              ("vite_temp", "frontend/node_modules/.vite-temp")):
            assert metadata(root / relative) == snapshot[key], (name, key)
    summary = json.loads((RAW / "verification-summary.json").read_bytes())
    for label, pair in summary["pairs"].items():
        before = (RAW / (label+"-before.json")).read_bytes()
        after = (RAW / (label+"-after.json")).read_bytes()
        assert sha(before) == pair["before_sha256"]
        assert sha(after) == pair["after_sha256"] and before == after
        protected = json.loads(before)
        assert {k: protected[k] for k in state} == state
    assert len(summary["pairs"]) == 17
    for name in ("final-after.json", "report-freeze-after.json"):
        protected = json.loads((RAW / name).read_bytes())
        assert {k: protected[k] for k in state} == state
    xml = {}
    for name, declared in manifest["xml"].items():
        data = (RAW / name).read_bytes()
        cases = list(ET.fromstring(data).iter("testcase"))
        actual = dict(tests=len(cases), failure=sum(c.find("failure") is not None for c in cases),
                      error=sum(c.find("error") is not None for c in cases),
                      skip=sum(c.find("skipped") is not None for c in cases))
        assert actual == {k: declared[k] for k in actual} and sha(data) == declared["sha256"], name
        xml[name] = actual
    assert len(xml) == 16
    assert xml["minimum.xml"] == dict(tests=4, failure=3, error=0, skip=0)
    assert xml["prod-minimum-zero.xml"] == dict(tests=2, failure=2, error=0, skip=0)
    for counts in ((0, 0), (19, 20), (20, 19), (20, 20)):
        minimum = json.loads((RAW / f"minimum/minimum-{counts[0]}-{counts[1]}.json").read_bytes())
        valid = counts == (20, 20)
        assert minimum["repository_accepts"] == valid
        assert len([r for r in minimum["active"]["gate_receipts"] if r["health_source"]]) == 2
    config_count = 0
    secrets = set()
    maps = [os.environ]
    for root in (ROOT, ROOT.with_name("eduagent")):
        for relative in (".env", "python/.env", "frontend/.env", ".env.local"):
            path = root / relative
            if path.is_file():
                config_count += 1
                maps.append(dotenv_values(path, interpolate=False))
    for values in maps:
        for key, value in values.items():
            if (re.search(r"(?:API_KEY|API_TOKEN|SIGNING_SECRET|ASSIGNMENT_SECRET|OPS_API_TOKEN)$", key)
                    and value and len(value) >= 12 and not value.startswith("${")):
                secrets.add(value.encode())

    def scan(data, name):
        assert not re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data), name
        assert not re.search(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", data), name
        for value in secrets:
            assert value not in data, name

    zips = members = 0
    for name, digest in manifest["files"].items():
        path = Path(name)
        assert not path.is_absolute() and ".." not in path.parts
        data = (RAW / path).read_bytes()
        assert sha(data) == digest, name
        scan(data, name)
        if path.suffix == ".zip":
            zips += 1
            with zipfile.ZipFile(io.BytesIO(data)) as zipped:
                assert zipped.testzip() is None
                for entry in zipped.infolist():
                    if not entry.is_dir():
                        scan(zipped.read(entry), name+":"+entry.filename)
                        members += 1
    resource_check = asyncio.run(resources())
    DEST.mkdir()
    for name in manifest["files"]:
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RAW / name, target)
    shutil.copyfile(RAW / "manifest.json", DEST / "manifest.json")
    shutil.copyfile(__file__, DEST / "parent-retain.py")
    REPORT.write_bytes(report)
    retained = {str(p.relative_to(DEST)): sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file()}
    proof = dict(verified_at=datetime.now(UTC).isoformat(),
                 role="parent byte-exact failure retention; not SPEC/CODE acceptance",
                 head=HEAD, source_count=354, source_sha256=combined(source),
                 raw_payload_count=466, raw_manifest_sha256=sha(mb),
                 raw_payload_sha256=manifest["payload_sha256"], report_sha256=sha(report),
                 retained_files=retained, preexisting_git_blobs=preexisting, xml=xml,
                 full_equal_snapshot_pairs=17, final_equal_snapshots=2, zip_crc_checked=zips,
                 zip_members_secret_checked=members,
                 secret_scan=dict(local_config_files=config_count, distinct_values=len(secrets), matches=0),
                 resource_check=resource_check,
                 valid_failure="SPEC-1: below frozen cohort minima authenticates Canary and Active chain",
                 unused_local_assertion_not_acceptance_basis=True,
                 automatic_promotion_bypass_not_proven=True,
                 model_calls=0, new_cost_usd="0",
                 raw_whitespace_preserved=True)
    (DEST / "parent-retention.json").write_text(json.dumps(proof, indent=2)+"\n")
    print(json.dumps({k: v for k, v in proof.items()
                      if k not in ("retained_files", "preexisting_git_blobs", "xml")}, indent=2))


if __name__ == "__main__":
    main()
