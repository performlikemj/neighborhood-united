# shared/pydantic_models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class FollowUpListItem(BaseModel):
    recommendation: str


class FollowUpList(BaseModel):
    items: List[FollowUpListItem]
