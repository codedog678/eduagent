"""父侧补核完整秘密扫描、TAR正文及历史manifest原分类，不改原证据。"""
import importlib.util
import io
import json
from datetime import UTC, datetime
from pathlib import Path
import tarfile

spec = importlib.util.spec_from_file_location("parent", "/tmp/m3-task9-metrics-code-fail-retain.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
c, E, ROOT, PRIMARY = p.c, p.E, p.ROOT, p.PRIMARY
OUT = Path("/tmp/m3-task9-metrics-code-archive-supplement.json")


def main():
    assert not OUT.exists()
    started = datetime.now(UTC).isoformat()
    state = p.read("initial-snapshot.json")
    p.protect(state)
    historical = p.read("historical-full-raw-audit.json")
    manifests = {}
    for name, declared in historical["manifests"].items():
        path = ROOT / c.safe_relative(name)
        data = path.read_bytes()
        assert c.sha(data) == declared["sha256"]
        obj = json.loads(data)
        mapping = obj.get("files", obj.get("files_sha256"))
        assert isinstance(mapping, dict)
        checked, missing, mismatch = [], [], []
        for relative, digest in mapping.items():
            target = path.parent / c.safe_relative(relative)
            if not target.is_file():
                missing.append(relative)
            elif c.sha(target.read_bytes()) == digest:
                checked.append(relative)
            else:
                mismatch.append(dict(
                    path=relative, expected=digest, actual=c.sha(target.read_bytes()),
                    samebyte_retained_paths=[
                        str(q.relative_to(ROOT)) for q in path.parent.glob("*")
                        if q.is_file() and c.sha(q.read_bytes()) == digest
                    ],
                ))
        actual = dict(sha256=c.sha(data), declared=len(mapping), checked=len(checked),
                      missing=missing, mismatch=mismatch, payload_sha256=c.combined(mapping))
        assert actual == declared, name
        if obj.get("payload_sha256") is not None:
            assert c.combined(mapping) == obj["payload_sha256"]
        manifests[name] = actual
    assert len(manifests) == 18
    old_source = json.loads((ROOT / "docs/superpowers/reports/task9-health-binding-fix-evidence/source-manifest.json").read_bytes())
    assert c.combined(old_source["files_sha256"]) == old_source["authoritative_sha256"]
    c.blobs(ROOT, "2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d", old_source["files_sha256"])
    assert len(old_source["files_sha256"]) == 352
    configs, secrets = c.secret_values((ROOT, PRIMARY))
    files = {
        str(root / name): digest for label, root in (("m3", ROOT), ("primary", PRIMARY))
        for name, digest in state[label]["tracked"].items()
    }
    files.update({str(q): c.sha(q.read_bytes()) for q in E.rglob("*") if q.is_file()})
    for path in (p.RESULT, p.SEAL, p.FINAL, p.PROOF, Path(__file__),
                 Path("/tmp/m3-task9-metrics-code-fail-retain.py"),
                 Path("/tmp/m3-task9-leaf-spec-pass-postcommit.json"),
                 Path("/tmp/m3-task9-leaf-spec-pass-commit.log")):
        files[str(path)] = c.sha(path.read_bytes())
    zips = members = tars = tar_members = 0
    classified = set()
    for name, digest in files.items():
        path = Path(name)
        data = path.read_bytes()
        assert c.sha(data) == digest
        p.scan(data, name, secrets, classified)
        if path.suffix == ".zip":
            zips += 1
            members += len(p.zip_members(data, name, secrets, classified))
        elif path.suffix == ".tar" or path.name.endswith((".tar.gz", ".tgz")):
            tars += 1
            actual = {}
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                for member in archive.getmembers():
                    c.safe_relative(member.name)
                    if member.isfile():
                        body = archive.extractfile(member).read()
                        p.scan(body, name + ":" + member.name, secrets, classified)
                        actual[member.name] = dict(bytes=len(body), sha256=c.sha(body))
                        tar_members += 1
            relative = str(path.relative_to(ROOT))
            assert actual == historical["records"][relative]["tar_members"]
    assert (zips, members, tars, tar_members) == (826, 29194, 1, 358)
    assert len(classified) == len(secrets) == 2
    p.protect(state)
    out = dict(
        started_at=started, finished_at=datetime.now(UTC).isoformat(),
        role="parent CODE FAIL archive/secrets supplement; not acceptance",
        head=p.HEAD, files=len(files), file_hashes=files,
        manifests=manifests, source_manifest_actual_historical_gitblobs=352,
        zip_files=zips, zip_members=members, tar_files=tars, tar_members=tar_members,
        secret_scan=dict(config_files=configs, distinct_actual_values=len(secrets),
                         matches=0, classified_exact_old_literals=sorted(classified)),
        both_trees_protected=True, model_requests=0, actual_cost_usd="0",
    )
    text = json.dumps(out, indent=2) + "\n"
    p.scan(text.encode(), str(OUT), secrets, classified)
    OUT.write_text(text)
    print(json.dumps({k: v for k, v in out.items() if k not in ("file_hashes", "manifests")}, indent=2))


if __name__ == "__main__":
    main()
