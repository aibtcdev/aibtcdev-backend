from fastapi import APIRouter, HTTPException
from typing import List
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from db.supabase_client import supabase
from db.helpers import get_public_crews

# Define the router for this module
router = APIRouter()


# Pydantic models for response structure
class Creator(BaseModel):
    email: str


class Task(BaseModel):
    id: int
    description: str
    expected_output: str
    agent_id: int
    profile_id: str


class Agent(BaseModel):
    id: int
    name: str
    role: str
    goal: str
    backstory: str
    agent_tools: List[str]
    tasks: List[Task]


class Crew(BaseModel):
    id: int
    name: str
    description: str
    created_at: str
    creator_email: str
    agents: List[Agent]


@router.get("/public-crews", response_model=List[Crew])
async def api_get_public_crews():
    try:
        crews = get_public_crews()
        return JSONResponse(content=crews)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching public crews: {str(e)}"
        )
