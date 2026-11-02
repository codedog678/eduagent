"""父侧只读证据复算工具；哈希、XML和资源核对不替代独立规格或代码验收。"""
import asyncio
import hashlib
import io
import json
import os
import re
import socket
import subprocess
import tarfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

os.environ["GIT_OPTIONAL_LOCKS"] = "0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def combined(mapping):
    return sha(json.dumps(sorted(mapping.items()), ensure_ascii=True,
                          separators=(",", ":")).encode())


def git(root, *args, **kwargs):
    return subprocess.check_output(["git", *args], cwd=root, **kwargs)


def names(root, *args):
    return {p.decode() for p in git(root, *args).split(b"\0") if p}


def blobs(root, revision, mapping):
    # 批量读取实际 Git blob，不以工作树哈希代替冻结版本。
    data = git(root, "cat-file", "--batch",
               input="".join(f"{revision}:{p}\n" for p in mapping).encode())
    pos = 0
    for path, digest in mapping.items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert len(header) == 3 and header[1] == b"blob", path
        size = int(header[2])
        pos = end + 1
        assert sha(data[pos:pos + size]) == digest, path
        pos += size + 1
    assert pos == len(data)


def worktree(root, mapping):
    for path, digest in mapping.items():
        assert sha((root / path).read_bytes()) == digest, path


def metadata(path):
    entries = []
    if path.exists():
        for entry in [path, *sorted(path.rglob("*"))]:
            stat = entry.lstat()
            entries.append((str(entry.relative_to(path)), stat.st_mode,
                            stat.st_size, stat.st_mtime_ns, stat.st_ino))
    return {"entries": len(entries), "sha256": sha(json.dumps(entries).encode())}


def protected(root, state, check_index=True):
    assert git(root, "rev-parse", "HEAD").decode().strip() == state["head"]
    assert not git(root, "status", "--porcelain")
    worktree(root, state["tracked"])
    if check_index:
        index = Path(git(root, "rev-parse", "--git-path", "index").decode().strip())
        if not index.is_absolute():
            index = root / index
        assert sha(index.read_bytes()) == state["index_sha256"]
        assert index.stat().st_mtime_ns == state["index_mtime_ns"]
    for key, relative in (("venv", ".venv"), ("vite", "frontend/node_modules/.vite"),
                          ("vite_temp", "frontend/node_modules/.vite-temp")):
        assert metadata(root / relative) == state[key], (root.name, key)


def xml_counts(data):
    cases = list(ET.fromstring(data).iter("testcase"))
    failures = sum(c.find("failure") is not None for c in cases)
    errors = sum(c.find("error") is not None for c in cases)
    skips = sum(c.find("skipped") is not None for c in cases)
    return dict(tests=len(cases), passed=len(cases)-failures-errors-skips,
                failure=failures, error=errors, skip=skips)


def secret_values(roots):
    from dotenv import dotenv_values
    values = set()
    config_count = 0
    mappings = [os.environ]
    for root in roots:
        for relative in (".env", "python/.env", "frontend/.env", ".env.local"):
            path = root / relative
            if path.is_file():
                config_count += 1
                mappings.append(dotenv_values(path, interpolate=False))
    for mapping in mappings:
        for key, value in mapping.items():
            if (re.search(r"(?:API_KEY|API_TOKEN|SIGNING_SECRET|ASSIGNMENT_SECRET|OPS_API_TOKEN)$", key)
                    and value and len(value) >= 12 and not value.startswith("${")):
                values.add(value.encode())
    return config_count, values


def scan_bytes(data, name, values):
    # 仅输出路径和断言结果，绝不回显匹配到的秘密。
    assert not re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data), name
    assert not re.search(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", data), name
    for value in values:
        assert value not in data, name


def safe_relative(name):
    path = Path(name)
    assert not path.is_absolute() and ".." not in path.parts, name
    return path


def check_archive(directory, manifest, values):
    files = manifest["files"]
    assert combined(files) == manifest["payload_sha256"]
    if "payload_count" in manifest:
        assert len(files) == manifest["payload_count"]
    zips = zip_members = tars = tar_members = 0
    xml = {}
    for name, digest in files.items():
        path = safe_relative(name)
        data = (directory / path).read_bytes()
        assert sha(data) == digest, name
        scan_bytes(data, name, values)
        if path.suffix == ".xml":
            xml[name] = xml_counts(data)
        if path.suffix == ".zip":
            zips += 1
            with zipfile.ZipFile(io.BytesIO(data)) as zipped:
                assert zipped.testzip() is None, name
                for member in zipped.infolist():
                    safe_relative(member.filename)
                    if not member.is_dir():
                        scan_bytes(zipped.read(member), name+":"+member.filename, values)
                        zip_members += 1
        if path.suffix == ".tar" or path.name.endswith((".tar.gz", ".tgz")):
            tars += 1
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
                for member in tar.getmembers():
                    safe_relative(member.name)
                    if member.isfile():
                        scan_bytes(tar.extractfile(member).read(), name+":"+member.name, values)
                        tar_members += 1
    return dict(files=len(files), payload_sha256=combined(files), xml=xml,
                zip_crc_checked=zips, zip_members_secret_checked=zip_members,
                tar_archives_checked=tars, tar_members_secret_checked=tar_members)


def check_snapshot_pairs(directory, pairs, expected_primary, expected_source):
    # 完整前后快照比较，不能仅挑选源码或给出局部“未变”结论。
    for label, declaration in pairs.items():
        before_name = label if label.endswith("-before.json") else label+"-before.json"
        after_name = before_name.replace("-before.json", "-after.json")
        before = (directory / before_name).read_bytes()
        after = (directory / after_name).read_bytes()
        assert before == after, label
        assert sha(before) == declaration["before_sha256"], label
        assert sha(after) == declaration["after_sha256"], label
        state = json.loads(before)
        assert state["primary"] == expected_primary, label
        assert state["m3"]["source"] == expected_source, label
    return len(pairs)


async def check_databases(port, database_names, data_dir, pid):
    import asyncpg
    connection = await asyncpg.connect(user="postgres", database="postgres",
                                       host="127.0.0.1", port=port)
    try:
        remaining = await connection.fetch(
            "SELECT datname FROM pg_database WHERE datname=ANY($1::text[])",
            list(database_names))
        actual_dir = await connection.fetchval("SHOW data_directory")
        version = await connection.fetchval("SHOW server_version")
    finally:
        await connection.close()
    assert not remaining, "declared owned databases remain"
    assert Path(actual_dir).resolve() == Path(data_dir).resolve()
    assert int((Path(actual_dir) / "postmaster.pid").read_text().splitlines()[0]) == pid
    return dict(exact_databases=len(database_names), remaining=0,
                shared_pg_port=port, shared_pg_pid=pid, version=version)


def closed_ports(ports):
    result = {}
    for port in ports:
        with socket.socket() as client:
            client.settimeout(1)
            result[str(port)] = client.connect_ex(("127.0.0.1", int(port))) != 0
    assert all(result.values()), result
    return result
