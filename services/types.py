from enum import Enum
from pydantic import BaseModel
from typing import Any, Dict, Optional

class TweetType(str, Enum):
    TOOL_REQUEST = "tool_request"
    CONVERSATION = "thread"
    INVALID = "invalid"

class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    priority: int = 1

class TweetAnalysisOutput(BaseModel):
    worthy: bool
    reason: str
    tweet_type: TweetType
    tool_request: Optional[ToolRequest] = None
    confidence_score: float

class TweetResponseOutput(BaseModel):
    response: str
    tone: str
    hashtags: list[str]
    mentions: list[str]
    urls: list[str]

class ToolResponseOutput(BaseModel):
    success: bool
    status: str
    message: str
    details: Dict[str, Any]
    input_parameters: Dict[str, Any]

class TweetAnalysisState(BaseModel):
    is_worthy: bool = False
    tweet_type: TweetType = TweetType.INVALID
    tool_request: Optional[ToolRequest] = None
    response_required: bool = False
    tweet_text: str = ""
    filtered_content: str = ""
    analysis_complete: bool = False
    tool_result: Optional[str] = None
    response: Optional[TweetResponseOutput] = None
    tool_success: bool = False
