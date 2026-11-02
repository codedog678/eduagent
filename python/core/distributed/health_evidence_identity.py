"""Pure identity and cohort relationships for already bounded frozen evidence."""

from collections import Counter
from uuid import UUID

from .contracts import canonical_hash


def observation_key(run_id, deployment_id, cohort, metric_contract_version):
    return canonical_hash({
        "run_id": str(UUID(str(run_id))), "deployment_id": str(UUID(str(deployment_id))),
        "cohort": cohort, "metric_contract_version": metric_contract_version,
    })


def same_distribution(candidate, stable):
    if not candidate or not stable or any(row.rehearsal_id is None for row in candidate + stable):
        return False
    c = Counter((row.rehearsal_id, row.operation) for row in candidate)
    s = Counter((row.rehearsal_id, row.operation) for row in stable)
    return c.keys() == s.keys() and all(
        c[bucket] * len(stable) == s[bucket] * len(candidate) for bucket in c
    )


def frozen_leaf_identity_matches(candidate, stable, window, *, cohort, passed, max_runs):
    """不查询、不评估、不写入；非 passed 保留合法的未配齐诊断窗口。"""
    if len(candidate) > max_runs or len(stable) > max_runs:
        return False
    flat = [row.observation_key for row in candidate + stable]
    if (
        len(set(flat)) != len(flat)
        or window.observation_start_key != (flat[0] if flat else canonical_hash([]))
        or window.observation_end_key != (flat[-1] if flat else canonical_hash([]))
        or (passed and window.triggered_thresholds != [])
    ):
        return False
    for rows in (candidate, stable):
        if rows != sorted(rows, key=lambda row: (row.observed_at, row.observation_key)):
            return False
        if any(row.observation_key != observation_key(
            row.run_id, row.deployment_id, row.cohort, row.metric_contract_version,
        ) for row in rows):
            return False
    if not passed:
        return True
    if cohort == "shadow":
        return {str(row.run_id) for row in candidate} == {str(row.run_id) for row in stable}
    return same_distribution(candidate, stable) and all(
        row.state_namespace != "production" for row in candidate + stable
    )
