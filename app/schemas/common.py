from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一响应结构。"""

    code: int
    message: str
    data: Any | None = None
