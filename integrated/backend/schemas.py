from typing import Any, Optional
from pydantic import BaseModel, Field


class SelectedElement(BaseModel):
    type: str
    tag: Optional[str] = None
    role: Optional[str] = None
    label: Optional[str] = None
    text: Optional[str] = None


class WebsiteContext(BaseModel):
    url: str
    hostname: str
    title: Optional[str] = None
    website_id: str = "unknown"
    page_type: str = "unknown"
    project: Optional[str] = None
    selected_component: Optional[dict[str, Any]] = None
    available_elements: list[dict[str, Any]] = Field(default_factory=list)
    page_summary: Optional[str] = None
