from __future__ import annotations

from .promotion_contracts import PolicyExecutionBinding


class ProtocolIdentityError(ValueError):
    """A business result does not identify its frozen Run binding."""


def validate_business_result(result: object, binding: PolicyExecutionBinding) -> None:
    execution = result.get("execution") if isinstance(result, dict) else None
    if not isinstance(execution, dict):
        raise ProtocolIdentityError("business result identity metadata is missing or malformed")
    expected = {
        "deployment_id": str(binding.deployment_id),
        "effective_policy_hash": binding.effective_policy_hash,
        "policy_cohort": binding.policy_cohort,
        "state_namespace": binding.state_namespace,
        "rehearsal_id": binding.rehearsal_id,
    }
    # Presence matters even for a production Run's explicit null rehearsal ID.
    for name, value in expected.items():
        if name not in execution or execution[name] != value:
            raise ProtocolIdentityError(f"business result identity differs at {name}")
