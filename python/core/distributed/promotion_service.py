from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .promotion_contracts import (
    DeploymentSnapshot,
    GateReceipt,
    PolicyArtifact,
)


class QualificationMaterial(BaseModel):
    """Frozen campaign evidence accepted by the promotion control plane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1, le=1)
    campaign_id: str = Field(min_length=1, max_length=128)
    campaign_binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact: PolicyArtifact
    receipts: list[GateReceipt] = Field(min_length=1)
    budget: dict[str, Any]

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
