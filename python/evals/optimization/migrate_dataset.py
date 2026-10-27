"""显式产生新版本开发集，保留原材料；不覆盖原数据或原分数。"""

import argparse
import json
from pathlib import Path

from evals.live_cases import load_live_cases
from evals.semantic_contract import required_semantics


def migrate(source: Path, target: Path):
    cases = load_live_cases(source)
    rows = []
    for case in cases:
        row = case.model_dump(by_alias=True, exclude_none=True)
        row["schema"] = "eduagent.tutor-live-review.v2"
        row["hard_checks"] = [
            check for check in row["hard_checks"] if not check["id"].startswith("S")
        ] + required_semantics(case)
        rows.append(json.dumps(row, ensure_ascii=False))
    with target.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(rows) + "\n")
    load_live_cases(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    migrate(args.source, args.target)
