# shared/pydantic_models.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

class FollowUpListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommendation: str

class FollowUpList(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: List[FollowUpListItem]