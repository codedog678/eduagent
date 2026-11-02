"""Independent Active assertions, not blocked by the earlier local failure."""

import json
import os
from pathlib import Path

import pytest

from tests.distributed.test_policy_health import health_repo
from tests.distributed.test_ops_complete_chain import sources
from test_fresh_leaf_identity import altered_leaf

pytestmark = pytest.mark.distributed_integration


@pytest.mark.parametrize("poison", [
    "valid", "noncanonical_key", "production_namespace",
    "wrong_distribution", "start_key", "triggered_pass",
])
async def test_fresh_active_requires_authoritatively_valid_exact_leaf(health_repo, poison):
    proof = await altered_leaf(health_repo, "canary", poison)
    directory = Path(os.environ["REVIEW_OWN"]) / os.environ["EVIDENCE_RUN"]
    directory.mkdir(exist_ok=True)
    with (directory / f"active-{poison}.json").open("x") as out:
        json.dump(proof, out, indent=2, default=str)
        out.write("\n")
    valid = poison == "valid"
    assert proof["authority_accepts"] == valid
    assert set(sources(proof["active"])) == (
        {"canary_health", "shadow_health"} if valid else set()
    ), "invalid exact Canary leaf must invalidate the entire Active consumed chain"
