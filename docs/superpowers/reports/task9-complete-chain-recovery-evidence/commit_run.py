import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime

import bootstrap

OWN, ROOT = bootstrap.OWN, bootstrap.ROOT
mode = sys.argv[1]
directory = "docs/superpowers/reports/task9-complete-chain-recovery-evidence"
paths = ["python/core/distributed/ops_queries.py",
         "python/tests/distributed/test_ops_complete_chain.py"] if mode == "product" else [directory]
assert bootstrap.git(ROOT, "diff", "--cached", "--name-only") == b""
stage = ["git", "add", *(["-f"] if mode == "evidence" else []), "--", *paths]
subprocess.run(stage, cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
staged = bootstrap.git(ROOT, "diff", "--cached", "--name-only", "-z").split(b"\0")
staged = [p.decode() for p in staged if p]
if mode == "product":
    assert set(staged) == set(paths)
else:
    assert all(p.startswith(directory + "/") for p in staged)
    manifest = json.loads((ROOT / directory / "manifest.json").read_text())
    assert set(staged) == {directory + "/" + p for p in manifest["files"]} | {directory + "/manifest.json"}
patterns = {
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "provider_key": rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{28,}",
    "github_token": rb"\bgh[pousr]_[A-Za-z0-9]{30,}",
    "jwt": rb"\beyJ[A-Za-z0-9_-]{25,}\.eyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}",
}
hits = []
members_checked = 0
for p in staged:
    path = ROOT / p
    assert not path.is_symlink()
    assert path.suffix not in (".sqlite", ".sqlite3", ".db", ".pyc")
    assert path.name not in (".env", ".DS_Store", "tool-install.log")
    content = {"file": path.read_bytes()}
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            content.update({name: z.read(name) for name in z.namelist()})
            members_checked += len(z.namelist())
    for member, data in content.items():
        for name, pattern in patterns.items():
            if re.search(pattern, data):
                hits.append(dict(file=p, member=member, pattern=name))
assert not hits, hits
record = {
    "role": "implementer staged-path and narrow sensitive-pattern check, not code/security review",
    "mode": mode, "stage_command": stage, "staged_paths": staged,
    "staged_sha256": {p: bootstrap.sha(bootstrap.git(ROOT, "show", ":" + p)) for p in staged},
    "secret_patterns": list(patterns), "secret_hits": hits, "zip_members_checked": members_checked,
    "parent": bootstrap.git(ROOT, "rev-parse", "HEAD").decode().strip(),
    "script": str(OWN / f"commit-{mode}.sh"), "started_at": datetime.now(UTC).isoformat(),
}
if mode == "product":
    (OWN / "staged-product.diff").write_bytes(bootstrap.git(ROOT, "diff", "--cached"))
try:
    result = subprocess.run(["bash", str(OWN / f"commit-{mode}.sh")], cwd=ROOT)
    record["exit"] = result.returncode
finally:
    record["finished_at"] = datetime.now(UTC).isoformat()
    record["head"] = bootstrap.git(ROOT, "rev-parse", "HEAD").decode().strip()
    if mode == "product":
        bootstrap.write(OWN / "product-commit-record.json", record)
    else:
        bootstrap.write(Path("/tmp/m3-task9-complete-chain-evidence-commit.json"), record)
assert result.returncode == 0
print(json.dumps({k: record[k] for k in ("mode", "parent", "head", "exit")}))
