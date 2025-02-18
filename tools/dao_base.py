from typing import Dict, Any, Optional
from pydantic import BaseModel

class DAOToolResponse(BaseModel):
    """Standard response format for DAO tools matching the Bun script ToolResponse format."""
    success: bool
    message: str
    data: Optional[Any] = None

    @classmethod
    def success_response(cls, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
        """Create a successful response"""
        return {
            "success": True,
            "message": message,
            "data": data
        }

    @classmethod
    def error_response(cls, message: str) -> Dict[str, Any]:
        """Create an error response"""
        return {
            "success": False,
            "message": message,
            "data": None
        }
