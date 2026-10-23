"""MRBench V1 的固定版本下载、校验和统一格式转换。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
import urllib.request
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from evals.io import DatasetError, write_cases, write_json
from evals.models import EvalCase, SourceMetadata

MRBENCH_REVISION = "bbef521ddb875f2cc8a5ee798f4066965a7cfd8a"
MRBENCH_ARCHIVE_SHA256 = (
    "ca2a342e47607df360184d35564376c3fc03dacf68658767c7d5225c28f6bbbd"
)
MRBENCH_ARCHIVE_URL = (
    "https://github.com/kaushal0494/UnifyingAITutorEvaluation/"
    f"archive/{MRBENCH_REVISION}.tar.gz"
)
MRBENCH_LICENSE = "CC BY-SA 4.0"
SOURCE_DATA = Path("MRBench") / "MRBench_V1.json"
CONVERTED_DATA = "mrbench-v1.eduagent.jsonl"
MANIFEST = "manifest.json"


def default_cache_dir() -> Path:
    root = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "eduagent" / "evals" / "mrbench"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_and_hash(source: BinaryIO, destination: Path) -> str:
    digest = hashlib.sha256()
    with destination.open("wb") as handle:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            handle.write(chunk)
    return digest.hexdigest()


def _cached_source(target: Path) -> Path | None:
    manifest_path = target / MANIFEST
    source_path = target / SOURCE_DATA
    if not manifest_path.exists() or not source_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        manifest.get("revision") != MRBENCH_REVISION
        or manifest.get("archive_sha256") != MRBENCH_ARCHIVE_SHA256
        or manifest.get("license") != MRBENCH_LICENSE
        or manifest.get("source_sha256") != _sha256(source_path)
    ):
        return None
    return source_path


def _download_archive(destination: Path) -> None:
    digest = hashlib.sha256()
    request = urllib.request.Request(
        MRBENCH_ARCHIVE_URL,
        headers={"User-Agent": "eduagent-eval/0.2"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        with destination.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                handle.write(chunk)
    actual = digest.hexdigest()
    if actual != MRBENCH_ARCHIVE_SHA256:
        raise DatasetError(
            f"MRBench archive checksum mismatch: {actual}; "
            f"expected {MRBENCH_ARCHIVE_SHA256}"
        )


def _select_member(archive: tarfile.TarFile, suffix: str) -> tarfile.TarInfo:
    matches = [
        member
        for member in archive.getmembers()
        if member.isfile() and member.name.endswith(suffix)
    ]
    if len(matches) != 1:
        raise DatasetError(
            f"MRBench archive expected one {suffix}, found {len(matches)}"
        )
    return matches[0]


def _extract_required(archive_path: Path, destination: Path) -> str:
    with tarfile.open(archive_path, "r:gz") as archive:
        readme_member = _select_member(archive, "/README.md")
        data_member = _select_member(archive, "/MRBench/MRBench_V1.json")
        readme_stream = archive.extractfile(readme_member)
        data_stream = archive.extractfile(data_member)
        if readme_stream is None or data_stream is None:
            raise DatasetError("MRBench archive contains unreadable required files")
        readme = readme_stream.read().decode("utf-8")
        if "CC BY-SA 4.0" not in readme:
            raise DatasetError("MRBench README does not declare CC BY-SA 4.0")
        (destination / "README.md").write_text(readme, encoding="utf-8")
        data_path = destination / SOURCE_DATA
        data_path.parent.mkdir(parents=True, exist_ok=True)
        return _copy_and_hash(data_stream, data_path)


def fetch_mrbench(
    cache_dir: str | Path | None = None,
    *,
    force: bool = False,
) -> Path:
    cache_root = Path(cache_dir) if cache_dir else default_cache_dir()
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / MRBENCH_REVISION
    cached = _cached_source(target)
    if cached is not None and not force:
        return cached
    if target.exists() and not force:
        raise DatasetError(
            f"MRBench cache is incomplete or corrupted: {target}; rerun with --force"
        )

    temporary = cache_root / f".{MRBENCH_REVISION}.{uuid.uuid4().hex}.tmp"
    archive_path: Path | None = None
    try:
        temporary.mkdir()
        descriptor, archive_name = tempfile.mkstemp(
            prefix="mrbench-",
            suffix=".tar.gz",
            dir=cache_root,
        )
        os.close(descriptor)
        archive_path = Path(archive_name)
        _download_archive(archive_path)
        source_sha = _extract_required(archive_path, temporary)
        write_json(temporary / MANIFEST, {
            "archive_sha256": MRBENCH_ARCHIVE_SHA256,
            "license": MRBENCH_LICENSE,
            "revision": MRBENCH_REVISION,
            "source": MRBENCH_ARCHIVE_URL,
            "source_path": str(SOURCE_DATA),
            "source_sha256": source_sha,
        })
        if force and target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
        return target / SOURCE_DATA
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    finally:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "unknown"


def _convert_item(item: dict[str, Any], index: int) -> list[EvalCase]:
    required = {
        "conversation_id",
        "conversation_history",
        "Data",
        "Split",
        "anno_llm_responses",
    }
    missing = sorted(required - item.keys())
    if missing:
        raise DatasetError(f"MRBench V1 item {index} missing fields: {missing}")
    responses = item["anno_llm_responses"]
    if not isinstance(responses, dict) or not responses:
        raise DatasetError(f"MRBench V1 item {index} has no annotated responses")

    converted: list[EvalCase] = []
    for model_name, response_data in responses.items():
        if not isinstance(response_data, dict):
            raise DatasetError(
                f"MRBench V1 item {index} response {model_name} is not an object"
            )
        response = response_data.get("response")
        annotations = response_data.get("annotation")
        if not isinstance(response, str) or not isinstance(annotations, dict):
            raise DatasetError(
                f"MRBench V1 item {index} response {model_name} is incomplete"
            )
        source_id = str(item["conversation_id"])
        converted.append(EvalCase(
            schema_version=1,
            case_id=(
                f"mrbench-v1-{index:03d}-{_slug(source_id)}-"
                f"{_slug(str(model_name))}"
            ),
            suite="mrbench-v1",
            kind="labeled_response",
            knowledge_id=None,
            input={
                "candidate_response": response,
                "conversation_history": item["conversation_history"],
                "ground_truth_solution": item.get("Ground_Truth_Solution"),
                "topic": item.get("Topic"),
            },
            expected={
                "annotations": annotations,
                "min_agreement": 0.0,
            },
            tags=["mrbench", _slug(str(item["Data"]))],
            source=SourceMetadata(
                name="MRBench V1",
                license=MRBENCH_LICENSE,
                source_id=source_id,
                revision=MRBENCH_REVISION,
                split=str(item["Split"]),
            ),
        ))
    return converted


def convert_mrbench(source_path: str | Path) -> Path:
    source = Path(source_path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"cannot read MRBench V1 data {source}: {exc}") from exc
    if not isinstance(raw, list) or len(raw) != 192:
        size = len(raw) if isinstance(raw, list) else type(raw).__name__
        raise DatasetError(f"MRBench V1 expected 192 conversations, found {size}")
    cases = [
        case
        for index, item in enumerate(raw)
        for case in _convert_item(item, index)
    ]
    identifiers = [case.case_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise DatasetError("MRBench conversion produced duplicate case IDs")
    destination = source.parent.parent / CONVERTED_DATA
    write_cases(destination, cases)
    manifest_path = source.parent.parent / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "converted_cases": len(cases),
        "converted_path": CONVERTED_DATA,
        "converted_sha256": _sha256(destination),
    })
    write_json(manifest_path, manifest)
    return destination


def fetch_and_convert(
    cache_dir: str | Path | None = None,
    *,
    force: bool = False,
) -> Path:
    return convert_mrbench(fetch_mrbench(cache_dir, force=force))
