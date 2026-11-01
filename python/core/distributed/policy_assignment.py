"""Admission-only token verification, deterministic assignment and artifact checks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from core.policy_store import BUILTIN_HASH, builtin_components, digest, validate_components
from core.tutor_policy import fixed_components

from .contracts import DistributedRunRequest
from .promotion_contracts import PolicyArtifact, PolicyExecutionBinding, RehearsalClaims
from .promotion_models import PolicyArtifactRecord
from .promotion_repository import PromotionRepository


class InvalidRehearsalToken(RuntimeError):
    def __init__(self):
        super().__init__("invalid rehearsal token")


class RehearsalTokenConflict(RuntimeError):
    def __init__(self):
        super().__init__("rehearsal token expired or already consumed")


class ArtifactUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("policy artifact unavailable or incompatible")


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def assignment_message(environment, deployment_id, learner_id, request_id):
    return b"\x00".join(value.encode("utf-8") for value in
        (environment, str(deployment_id), learner_id, request_id))


def assignment_bucket(*, secret: bytes, environment: str, deployment_id: str,
                      learner_id: str, request_id: str) -> int:
    if len(secret) < 32:
        raise ValueError("assignment secret must contain at least 32 bytes")
    message = assignment_message(environment, deployment_id, learner_id, request_id)
    return int.from_bytes(hmac.digest(secret, message, "sha256")[:8], "big") % 10000


def select_cohort(state: str, traffic_basis_points: int, bucket: int) -> str:
    return "candidate" if state == "active" or (
        state == "canary" and bucket < traffic_basis_points) else "stable"


class PolicyAssigner:
    def __init__(self, *, signing_secret: bytes | None = None,
                 assignment_secret: bytes | None = None,
                 allow_fault_injection: bool = False,
                 runtime_hash: str | None = None, source_revision: str | None = None,
                 settings_obj=None):
        for secret in (signing_secret, assignment_secret):
            if secret is not None and len(secret) < 32:
                raise ValueError("promotion secrets must contain at least 32 bytes")
        self._signing_secret = signing_secret
        self._assignment_secret = assignment_secret
        self.allow_fault_injection = allow_fault_injection
        self.runtime_hash = runtime_hash
        self.source_revision = source_revision
        self.settings = settings_obj

    def verify(self, token: str, spec: DistributedRunRequest, now: datetime) -> RehearsalClaims:
        if self._signing_secret is None or self._assignment_secret is None:
            raise InvalidRehearsalToken()
        try:
            if len(token) > 8192:
                raise ValueError("oversized token")
            encoded_body, encoded_signature = token.split(".")

            def decode(value):
                result = base64.b64decode(value + "=" * (-len(value) % 4),
                                         altchars=b"-_", validate=True)
                if base64.urlsafe_b64encode(result).decode().rstrip("=") != value:
                    raise ValueError("noncanonical encoding")
                return result

            body, signature = decode(encoded_body), decode(encoded_signature)
            if not hmac.compare_digest(hmac.digest(self._signing_secret, body, "sha256"), signature):
                raise ValueError("signature mismatch")
            values = json.loads(body)
            if canonical_json(values) != body:
                raise ValueError("noncanonical payload")
            claims = RehearsalClaims.model_validate(values)
            if (claims.namespace != f"rehearsal-{claims.rehearsal_id}"
                or claims.learner_id != spec.learner_id
                or claims.request_id != spec.request_id
                or spec.operation not in claims.operations
                or claims.issued_at > now
                or (claims.expires_at - claims.issued_at).total_seconds() > 3600
                or (claims.fault_profile != "none" and not self.allow_fault_injection)):
                raise ValueError("claims mismatch")
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise InvalidRehearsalToken() from None
        if claims.expires_at <= now:
            raise RehearsalTokenConflict()
        return claims

    async def load_artifact(self, session: AsyncSession, policy_hash: str):
        return await session.get(PolicyArtifactRecord, policy_hash)

    def validate_artifact(self, row: PolicyArtifactRecord | None):
        try:
            if row is None:
                raise ValueError("missing artifact")
            artifact = PolicyArtifact.model_validate({
                name: getattr(row, name) for name in PolicyArtifact.model_fields
            })
            components = artifact.components.model_dump(mode="json")
            validate_components(components)
            if artifact.fixed_components_hash != digest(fixed_components()):
                raise ValueError("fixed components mismatch")
            if artifact.policy_hash == BUILTIN_HASH:
                from .runtime import (BUILTIN_RUNTIME_HASH, BUILTIN_PROTOCOL_HASH,
                                      BUILTIN_PROPOSER_HASH)
                if (components != builtin_components() or artifact.data_role != "builtin"
                    or artifact.parent_policy_hash is not None
                    or artifact.runtime_hash != BUILTIN_RUNTIME_HASH
                    or artifact.source_revision != "builtin"
                    or artifact.protocol_hash != BUILTIN_PROTOCOL_HASH
                    or artifact.proposer_hash != BUILTIN_PROPOSER_HASH
                    or artifact.evidence_bindings != {}
                    or digest({"components": components, "fixed_components": fixed_components()}) != BUILTIN_HASH):
                    raise ValueError("builtin mismatch")
            else:
                from config.settings import settings
                from core.versions import policy_runtime_hash
                from evals.live_runner import code_revision

                runtime_hash = self.runtime_hash or policy_runtime_hash(self.settings or settings)
                source_revision = self.source_revision or code_revision()["python_source_sha256"]
                if (artifact.data_role != "holdout_validated"
                    or PromotionRepository._artifact_hash(artifact) != artifact.policy_hash
                    or artifact.runtime_hash != runtime_hash
                    or artifact.source_revision != source_revision):
                    raise ValueError("artifact integrity or compatibility mismatch")
            return artifact.components
        except (ValueError, ValidationError, AttributeError):
            raise ArtifactUnavailable() from None

    async def bind(self, session, deployment, spec, claims):
        environment = deployment.environment
        message = assignment_message(environment, deployment.deployment_id,
                                     spec.learner_id, spec.request_id)
        cohort = "stable"
        if claims is not None:
            if (environment != "rehearsal"
                or str(claims.deployment_id) != deployment.deployment_id
                or claims.deployment_version != deployment.version):
                raise InvalidRehearsalToken()
            bucket = assignment_bucket(secret=self._assignment_secret,
                environment=environment, deployment_id=deployment.deployment_id,
                learner_id=spec.learner_id, request_id=spec.request_id)
            cohort = select_cohort(deployment.state, deployment.traffic_basis_points, bucket)
        policy_hash = deployment.candidate_policy_hash if cohort == "candidate" else deployment.stable_policy_hash
        components = self.validate_artifact(await self.load_artifact(session, policy_hash))
        return PolicyExecutionBinding(
            deployment_id=deployment.deployment_id, environment=environment,
            effective_policy_hash=policy_hash, components=components, policy_cohort=cohort,
            assignment_key_hash=hashlib.sha256(message).hexdigest(),
            assignment_reason="production_stable" if claims is None else f"rehearsal_{deployment.state}_{cohort}",
            state_namespace="production" if claims is None else claims.namespace,
            rehearsal_id=None if claims is None else claims.rehearsal_id,
            rehearsal_fault_profile=claims.fault_profile if claims and cohort == "candidate" else "none",
            injected_latency_seconds=(
                Decimal(str(getattr(self.settings, "promotion_injected_latency_seconds", 0)))
                if claims and cohort == "candidate" and claims.fault_profile == "latency" else Decimal(0)
            ),
        )
