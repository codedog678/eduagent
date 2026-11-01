"""Freeze structured test/source evidence without hashing the manifest into itself."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

OWN = Path(__file__).parent
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PARENT = "517c04f137ed93ebb042ec4ff027d120d3625847"
FINAL = {"greenfinal", "relationsfreeze", "fullv2", "uifinalv2",
         "productioncurrentfinal", "productionhistoryfinal"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(name, body):
    (OWN / name).write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")


def count(cases):
    result = dict(executions=len(cases), passed=0, failures=0, errors=0, skipped=0)
    for case in cases:
        key = "errors" if case.find("error") is not None else \
            "failures" if case.find("failure") is not None else \
            "skipped" if case.find("skipped") is not None else "passed"
        result[key] += 1
    return result


def main():
    paths = subprocess.check_output([
        "git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard",
        "-z", "--", "python", "frontend",
    ]).decode().split("\0")
    source = {p: sha((ROOT / p).read_bytes()) for p in sorted(set(paths)) if p}
    authoritative = sha(json.dumps(sorted(source.items()), separators=(",", ":"), ensure_ascii=True).encode())
    source_identity = {
        "parent": PARENT, "source_count": len(source), "files_sha256": source,
        "authoritative_sha256": authoritative,
        "recipe": "sha256(json.dumps(sorted(path_sha256.items()),separators=(',',':'),ensure_ascii=True).encode())",
        "products_parent": "e29bdb4; parent HEAD only archives prior CODE failure",
        "baseline_source_sha256": "8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582",
    }
    dump("source-manifest.json", source_identity)
    attempts = {}
    for path in sorted(OWN.glob("*.xml")):
        tree = ET.parse(path)
        cases = list(tree.iter("testcase"))
        modules = {}
        for case in cases:
            modules.setdefault(case.get("classname", ""), []).append(case)
        attempts[path.stem] = {
            **count(cases), "sha256": sha(path.read_bytes()), "final_matrix": path.stem in FINAL,
            "suite": [s.attrib for s in tree.iter("testsuite")],
            "modules": {k: count(v) for k, v in modules.items()},
            "nonpass": [{"class": c.get("classname"), "name": c.get("name"),
                         "status": count([c])} for c in cases if not count([c])["passed"]],
        }
    dump("test-counts.json", attempts)
    full = list(ET.parse(OWN / "fullv2.xml").iter("testcase"))
    f1 = [c for c in full if c.get("name", "").startswith((
        "test_gate_tie_order_matches_publish_authority",
        "test_gate_order_excludes_unbound_or_future_pass",
    ))]
    assert count(f1) == dict(executions=9, passed=9, failures=0, errors=0, skipped=0)
    dump("f1-nine.json", {"counts": count(f1), "source": "fullv2.xml",
                         "cases": [c.get("name") for c in f1]})
    boundaries = {}
    baseline = json.loads((OWN / "c1redvalid-before.json").read_text())
    for path in sorted(OWN.glob("*-after.json")):
        state = json.loads(path.read_text())
        boundaries[path.name] = {key: state[key] == baseline[key]
                                for key in ("primary", "venv", "m3_vite_temp", "m3_vite_cache")}
    dump("readonly-boundaries.json", boundaries)
    products = []
    for name in ("currentfinal", "historyfinal"):
        body = json.loads((OWN / f"live-fixture-{name}.json").read_text())
        products.append({"name": name, "role": body["role"], "scenarios": body["scenarios"]})
    dump("production-identities.json", {
        "role": "synthetic engineering validation, not release qualification",
        "model_requests": 0, "model_cost_usd": "0",
        "protocol_hash": "b" * 64, "runtime_hash": "f" * 64, "source_revision": "test-source",
        "source_authoritative_sha256": authoritative, "fixtures": products,
    })
    print(json.dumps({"source_count": len(source), "source_sha": authoritative,
                      "final": {k: {n: v for n, v in attempts[k].items()
                                    if n in ("executions", "passed", "failures", "errors", "skipped", "sha256")}
                                for k in sorted(FINAL)},
                      "readonly": all(all(v.values()) for v in boundaries.values())}, indent=2))


if __name__ == "__main__":
    main()
