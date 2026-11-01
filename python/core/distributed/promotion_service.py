from __future__ import annotations

from typing import Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_serializer,
    model_validator,
)

from .promotion_contracts import (
    DeploymentSnapshot,
    GateReceipt,
    HealthDecision,
    PolicyArtifact,
)


def health_decision_from_window(window) -> HealthDecision:
    """Legacy wire 'rollback' means failed health, not proof that a head moved.

    Shadow failures remain historical and do not automatically roll back.
    Only the evaluator's transactional Canary/Active path can move the head.
    """
    return HealthDecision(
        decision="rollback" if window.decision == "fail" else window.decision,
        reasons=window.triggered_thresholds,
        candidate_run_count=window.candidate_stats["run_count"],
        stable_run_count=window.stable_stats["run_count"],
        evaluated_at=window.evaluated_at,
    )


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BudgetUsage(StrictFrozenModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    prompt_cache_hit_tokens: int = Field(default=0, ge=0)
    prompt_cache_miss_tokens: int = Field(default=0, ge=0)

    @model_serializer(mode="wrap")
    def serialize_supplied_cache_fields(self, handler):
        value = handler(self)
        for field in (
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        ):
            if field not in self.model_fields_set:
                value.pop(field, None)
        return value

    @model_validator(mode="after")
    def validate_cache_usage(self) -> BudgetUsage:
        cache_fields = {
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        }
        supplied = cache_fields & self.model_fields_set
        if supplied == cache_fields and (
            self.prompt_cache_hit_tokens + self.prompt_cache_miss_tokens
            != self.input_tokens
        ):
            raise ValueError(
                "cache-hit and cache-miss tokens must equal input tokens"
            )
        if (
            supplied != cache_fields
            and any(
                getattr(self, field) > self.input_tokens
                for field in supplied
            )
        ):
            raise ValueError("cache tokens cannot exceed input tokens")
        return self


class TokenRates(StrictFrozenModel):
    input_miss: float = Field(ge=0, allow_inf_nan=False)
    input_hit: float = Field(ge=0, allow_inf_nan=False)
    output: float = Field(ge=0, allow_inf_nan=False)


class BudgetPricingPeriods(StrictFrozenModel):
    peak: TokenRates
    off_peak: TokenRates


class BudgetPricing(StrictFrozenModel):
    source: str = Field(min_length=1, max_length=500)
    verified_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    currency: Literal["CNY"]
    model: str | None = Field(default=None, min_length=1, max_length=128)
    per_million_tokens: BudgetPricingPeriods


class BudgetRoles(StrictFrozenModel):
    task: int = Field(ge=0)
    judge: int = Field(ge=0)
    reflection: int = Field(ge=0)


class QualificationBudget(StrictFrozenModel):
    max_requests: int = Field(gt=0)
    max_cny: float = Field(gt=0, allow_inf_nan=False)
    requests: int = Field(ge=0)
    usage: BudgetUsage
    estimated_peak_cny: float = Field(ge=0, allow_inf_nan=False)
    estimated_off_peak_cny: float = Field(ge=0, allow_inf_nan=False)
    unconfirmed_reservation_cny: float = Field(
        ge=0,
        allow_inf_nan=False,
    )
    billing_status: Literal["estimate_only"]
    pricing: BudgetPricing
    pricing_note: str = Field(min_length=1, max_length=500)
    roles: BudgetRoles

    @model_validator(mode="after")
    def validate_totals(self) -> QualificationBudget:
        if self.requests > self.max_requests:
            raise ValueError("budget requests exceed max_requests")
        if sum(self.roles.model_dump().values()) != self.requests:
            raise ValueError("budget roles must account for every request")
        if self.estimated_peak_cny + self.unconfirmed_reservation_cny > (
            self.max_cny
        ):
            raise ValueError("budget estimate exceeds max_cny")
        return self


class QualificationMaterial(BaseModel):
    """Frozen campaign evidence accepted by the promotion control plane."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    campaign_id: str = Field(min_length=1, max_length=128)
    campaign_binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact: PolicyArtifact
    receipts: list[GateReceipt] = Field(min_length=1)
    budget: QualificationBudget

    @model_validator(mode="after")
    def unique_receipts(self) -> QualificationMaterial:
        gate_types = [receipt.gate_type for receipt in self.receipts]
        if len(gate_types) != len(set(gate_types)):
            raise ValueError("qualification contains duplicate gate receipts")
        return self


class QualificationRepository(Protocol):
    async def register_qualification(
        self,
        material: QualificationMaterial,
        *,
        actor: str,
        command_id: str,
    ) -> DeploymentSnapshot: ...


class AuthenticatedPrincipalMismatch(PermissionError):
    """The audit actor does not match the trusted transport principal."""


class _AuthenticatedCommandBoundary:
    def __init__(self, *, authenticated_principal: str) -> None:
        principal = authenticated_principal.strip()
        if not principal:
            raise ValueError("authenticated command principal is required")
        self.authenticated_principal = principal

    def _authorize_actor(self, actor: str) -> None:
        if actor != self.authenticated_principal:
            raise AuthenticatedPrincipalMismatch(
                "command actor must match authenticated principal"
            )


class PromotionService(_AuthenticatedCommandBoundary):
    """Authenticated boundary for campaign registration commands."""

    def __init__(
        self,
        repository: QualificationRepository,
        *,
        authenticated_principal: str,
    ) -> None:
        super().__init__(authenticated_principal=authenticated_principal)
        self.repository = repository

    async def register_campaign(
        self,
        campaign,
        *,
        actor: str,
        command_id: str,
    ) -> DeploymentSnapshot:
        self._authorize_actor(actor)
        material = QualificationMaterial.model_validate(
            campaign.qualification_material()
        )
        return await self.repository.register_qualification(
            material,
            actor=actor,
            command_id=command_id,
        )


class PromotionCommandRepository(QualificationRepository, Protocol):
    async def transition(self, command): ...

    async def get_head(self, environment: str) -> DeploymentSnapshot: ...

    async def get_snapshot(
        self, environment: str, version: int
    ) -> DeploymentSnapshot: ...


class PromotionCommandService(_AuthenticatedCommandBoundary):
    """Authenticated application write boundary for promotion commands."""

    def __init__(
        self,
        repository: PromotionCommandRepository,
        *,
        authenticated_principal: str,
    ) -> None:
        super().__init__(authenticated_principal=authenticated_principal)
        self.repository = repository

    async def register_campaign(
        self,
        campaign,
        *,
        actor: str,
        command_id: str,
    ) -> DeploymentSnapshot:
        self._authorize_actor(actor)
        material = QualificationMaterial.model_validate(
            campaign.qualification_material()
        )
        return await self.repository.register_qualification(
            material,
            actor=actor,
            command_id=command_id,
        )

    async def transition(self, command) -> DeploymentSnapshot:
        self._authorize_actor(command.actor)
        return await self.repository.transition(command)

    async def show_head(self, environment: str) -> DeploymentSnapshot:
        return await self.repository.get_head(environment)

    async def show_snapshot(
        self, environment: str, version: int
    ) -> DeploymentSnapshot:
        return await self.repository.get_snapshot(environment, version)


class RehearsalTokenIssuer:
    """Issues short-lived signed rehearsal claims without persisting tokens."""

    def __init__(
        self,
        repository: PromotionCommandRepository,
        *,
        signing_secret: str,
        assignment_secret: str,
        clock=None,
        allow_fault_injection: bool = False,
    ) -> None:
        if len(signing_secret) < 32 or len(assignment_secret) < 32:
            raise ValueError("promotion secrets must each contain 32 characters")
        self.repository = repository
        self._signing_secret = signing_secret.encode("utf-8")
        self._assignment_secret = assignment_secret.encode("utf-8")
        self.clock = clock
        self.allow_fault_injection = allow_fault_injection

    async def issue(
        self,
        *,
        rehearsal_id: str,
        namespace: str,
        learner_id: str,
        request_id: str,
        operation: str,
        fault_profile: str,
        ttl_seconds: int,
    ) -> dict[str, str]:
        import base64
        from datetime import UTC, datetime, timedelta
        import hashlib
        import hmac
        import json
        import secrets

        from .promotion_contracts import RehearsalClaims

        if not 30 <= ttl_seconds <= 3600:
            raise ValueError("ttl_seconds must be between 30 and 3600")
        canonical_namespace = f"rehearsal-{rehearsal_id}"
        if namespace != canonical_namespace:
            raise ValueError(
                "namespace must match the server-derived rehearsal namespace"
            )
        if fault_profile != "none" and not self.allow_fault_injection:
            raise ValueError("promotion fault injection is disabled")
        head = await self.repository.get_head("rehearsal")
        now = self.clock() if self.clock is not None else datetime.now(UTC)
        claims = RehearsalClaims(
            rehearsal_id=rehearsal_id,
            deployment_id=head.deployment_id,
            deployment_version=head.version,
            learner_id=learner_id,
            request_id=request_id,
            namespace=canonical_namespace,
            operations=[operation],
            fault_profile=fault_profile,
            nonce=secrets.token_hex(24),
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        body = json.dumps(
            claims.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(
            self._signing_secret,
            body,
            hashlib.sha256,
        ).digest()

        def encoded(value: bytes) -> str:
            return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

        assignment = b"\x00".join(
            part.encode("utf-8")
            for part in (
                head.environment,
                str(head.deployment_id),
                learner_id,
                request_id,
            )
        )
        bucket = int.from_bytes(
            hmac.new(
                self._assignment_secret,
                assignment,
                hashlib.sha256,
            ).digest()[:8],
            "big",
        ) % 10000
        expected_cohort = (
            "candidate"
            if head.state == "active"
            or (
                head.state == "canary"
                and bucket < head.traffic_basis_points
            )
            else "stable"
        )
        return {
            "token": f"{encoded(body)}.{encoded(signature)}",
            "expected_cohort": expected_cohort,
        }
