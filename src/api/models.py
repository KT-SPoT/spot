"""HTTP intake validation; the Scout contract remains SpotRequest v0.1."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IntakeModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=True)


class Store(IntakeModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=500)
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    lng: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def coordinates_together(self):
        if (self.lat is None) != (self.lng is None):
            raise ValueError("coordinates must be supplied together")
        return self


class Campaign(IntakeModel):
    purpose: str = Field(min_length=1, max_length=500)
    product: str = Field(min_length=1, max_length=300)
    target_hint: str | None = Field(default=None, max_length=500)


class Research(IntakeModel):
    reference_date: str = Field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())
    radius_m: int = Field(default=1000, ge=1, le=10000)
    lookback_days: int = Field(default=180, ge=0, le=3650)
    comparison_area: str | None = Field(default=None, max_length=500)

    @field_validator("reference_date")
    @classmethod
    def valid_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("expected YYYY-MM-DD")
        return value


class ResearchRequest(IntakeModel):
    schema_version: Literal["0.1"]
    request_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    requested_at: str | None = None
    store: Store
    campaign: Campaign
    research: Research = Field(default_factory=Research)

    @field_validator("requested_at")
    @classmethod
    def valid_timestamp(cls, value):
        if value is not None and datetime.fromisoformat(value).tzinfo is None:
            raise ValueError("timezone required")
        return value
