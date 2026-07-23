from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Page:
    page_number: int
    text: str

@dataclass
class Chunk:
    content: str
    metadata: Dict[str, Any]