"""MRBench 适配器只处理固定版本和显式许可。"""

import json
from pathlib import Path

import pytest

from evals.adapters import mrbench
from evals.io import DatasetError

FIXTURE = Path(__file__).parent / "fixtures" / "mrbench_item.json"


def test_authored_fixture_converts_to_labeled_case():
    item = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = mrbench._convert_item(item, 0)
    assert len(cases) == 1
    case = cases[0]
    assert case.kind == "labeled_response"
    assert case.source.license == "CC BY-SA 4.0"
    assert case.source.revision == mrbench.MRBENCH_REVISION
    assert case.expected["annotations"]["Providing_Guidance"] == "Yes"


def test_valid_cache_is_reused_without_network(tmp_path, monkeypatch):
    target = tmp_path / mrbench.MRBENCH_REVISION
    source = target / mrbench.SOURCE_DATA
    source.parent.mkdir(parents=True)
    source.write_text("[]", encoding="utf-8")
    (target / mrbench.MANIFEST).write_text(json.dumps({
        "archive_sha256": mrbench.MRBENCH_ARCHIVE_SHA256,
        "license": mrbench.MRBENCH_LICENSE,
        "revision": mrbench.MRBENCH_REVISION,
        "source_sha256": mrbench._sha256(source),
    }), encoding="utf-8")
    monkeypatch.setattr(
        mrbench,
        "_download_archive",
        lambda _: pytest.fail("valid cache should not download"),
    )
    assert mrbench.fetch_mrbench(tmp_path) == source


def test_corrupt_cache_requires_explicit_force(tmp_path):
    target = tmp_path / mrbench.MRBENCH_REVISION
    target.mkdir()
    with pytest.raises(DatasetError, match="incomplete or corrupted"):
        mrbench.fetch_mrbench(tmp_path)
