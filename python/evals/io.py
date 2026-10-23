"""JSONL 评测数据的严格读取和原子写入。"""

from __future__ import annotations

import json
import os
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from evals.models import EvalCase


class DatasetError(ValueError):
    """数据集格式、版本或内容不满足评测契约。"""


def builtin_dataset_path() -> Path:
    resource = files("evals.datasets").joinpath("builtin.jsonl")
    return Path(str(resource))


def load_cases(path: str | Path | None = None, suite: str | None = None) -> list[EvalCase]:
    source = Path(path) if path else builtin_dataset_path()
    cases: list[EvalCase] = []
    seen: set[str] = set()
    try:
        handle = source.open("r", encoding="utf-8")
    except OSError as exc:
        raise DatasetError(f"cannot read dataset {source}: {exc}") from exc

    with handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
                case = EvalCase.model_validate(value)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise DatasetError(f"{source}:{line_no}: {exc}") from exc
            if case.case_id in seen:
                raise DatasetError(f"{source}:{line_no}: duplicate case_id {case.case_id}")
            seen.add(case.case_id)
            if suite is None or case.suite == suite:
                cases.append(case)
    if not cases:
        selected = f" for suite {suite}" if suite else ""
        raise DatasetError(f"dataset {source} contains no cases{selected}")
    return cases


def write_cases(path: str | Path, cases: Iterable[EvalCase]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for case in cases:
                handle.write(case.model_dump_json())
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination


def write_json(path: str | Path, value: dict) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination
