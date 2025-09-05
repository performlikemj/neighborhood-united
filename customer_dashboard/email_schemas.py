"""
Pydantic schemas for router-driven email formatting.

These schemas represent structured data (not full HTML). Templates render the
final HTML using these fields.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class _StrictModel(BaseModel):
    """Base class that forbids unspecified fields to ensure JSON Schema
    includes additionalProperties: false as required by the Responses API."""
    model_config = ConfigDict(extra="forbid")


class EmailBody(_StrictModel):
    """Generic fallback schema."""
    main_text: str = Field(default="")
    final_text: str = Field(default="")
    css_classes: Optional[List[str]] = None


class CategoryItem(_StrictModel):
    ingredient: str
    quantity: str
    unit: Optional[str] = None
    notes: Optional[str] = None


class CategoryTable(_StrictModel):
    category: str
    items: List[CategoryItem]



class EmailShoppingList(_StrictModel):
    main_text: str
    shopping_tables: List[CategoryTable] = Field(default_factory=list)
    final_text: str


class EmailDailyPrep(_StrictModel):
    main_text: str
    sections_by_day: Optional[dict] = None  # {day: [step strings or structured]}
    final_text: str


class EmailBulkPrep(_StrictModel):
    main_text: str
    batch_sections: Optional[dict] = None  # {batch: [steps]}
    final_text: str


class EmailEmergencySupply(_StrictModel):
    main_text: str
    supplies_by_category: Optional[List[CategoryTable]] = None
    final_text: str


class EmailSystemUpdate(_StrictModel):
    main_text: str
    final_text: str


class EmailPaymentConfirmation(_StrictModel):
    main_text: str
    final_text: str


class EmailRefundNotification(_StrictModel):
    main_text: str
    final_text: str


class EmailOrderCancellation(_StrictModel):
    main_text: str
    final_text: str

