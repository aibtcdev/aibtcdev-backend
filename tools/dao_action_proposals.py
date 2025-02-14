from pydantic import BaseModel, Field

class DaoBaseInput(BaseModel):
    """Base input schema for dao tools that do not require parameters."""
    pass

