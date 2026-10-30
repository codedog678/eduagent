from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .promotion_contracts import (
    DeploymentSnapshot,
    GateReceipt,
    PolicyArtifact,
)


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BudgetUsage(StrictFrozenModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    prompt_cache_hit_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_cache_usage(self) -> BudgetUsage:
        if self.prompt_cache_hit_tokens > self.input_tokens:
            raise ValueError("cache-hit tokens cannot exceed input tokens")
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


class PromotionService:
    """Application boundary for registering campaign qualification evidence."""

    def __init__(self, repository: QualificationRepository) -> None:
        self.repository = repository

    async def register_campaign(
        self,
        campaign,
        *,
        actor: str,
        command_id: str,
    ) -> DeploymentSnapshot:
        material = QualificationMaterial.model_validate(
            campaign.qualification_material()
        )
        return await self.repository.register_qualification(
            material,
            actor=actor,
            command_id=command_id,
        )
