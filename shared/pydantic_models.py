# shared/pydantic_models.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

class FollowUpListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation: str


class FollowUpList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: List[FollowUpListItem]


class GeoCoordinates(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(..., description="Latitude")
    longitude: float = Field(..., description="Longitude")