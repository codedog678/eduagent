import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

OWN = Path("/tmp/m3-task9-spec-independent")
result = {"scope": "Independent Task9 SPEC, synthetic non-release verification", "junit": {}, "sha256": {}}
for path in sorted(OWN.glob("*.xml")):
    root = ET.parse(path).getroot()
    suites = list(root.iter("testsuite"))
    counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    assert len(list(root.iter("testcase"))) == counts["tests"]
    result["junit"][path.name] = counts
    print(path.name, counts)
paths = list(OWN.glob("*.log")) + list(OWN.glob("*.xml")) + list(OWN.glob("*.py")) + list(OWN.glob("*.sh"))
paths += list((OWN / "screenshots").glob("*.png"))
paths += list((OWN / "screenshots-isolated").glob("*.png"))
paths += list((OWN / "frontend/live-e2e").glob("*.ts"))
paths += [OWN / "frontend/playwright.live.config.ts"]
paths += list(OWN.glob("live-fixture*.json"))
for path in sorted(paths):
    result["sha256"][str(path.relative_to(OWN))] = hashlib.sha256(path.read_bytes()).hexdigest()
(OWN / "independent-manifest.json").write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n")
for name in ("targeted-final.xml", "gate-tie-final.xml", "ui-isolated.xml", "ui-live-isolated.xml", "build-isolated.log"):
    print(name, result["sha256"][name])
