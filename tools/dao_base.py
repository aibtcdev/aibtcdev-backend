from typing import Dict, Any, Optional
from pydantic import BaseModel

class DAOToolResponse(BaseModel):
    """Standard response format for DAO tools."""
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def success_response(cls, output: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a successful response"""
        return {
            "success": True,
            "output": output,
            "error": None,
            "metadata": metadata
        }

    @classmethod
    def error_response(cls, error: str, output: str = "") -> Dict[str, Any]:
        """Create an error response"""
        return {
            "success": False,
            "output": output,
            "error": error,
            "metadata": None
        }
