from pydantic import BaseModel
from typing import List, Optional

class FAQRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"

class FAQResponse(BaseModel):
    answer: str
    sources: List[str]
    confident: bool
    is_property_query: bool
    redirect: Optional[str] = None