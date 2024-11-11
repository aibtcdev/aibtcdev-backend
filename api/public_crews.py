from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
from db.supabase_client import supabase

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

def mask_email(email: str) -> str:
    """Mask the @stacks.id part of the email and capitalize the username."""
    if '@stacks.id' in email:
        username = email.split('@')[0]
        return username.upper()
    return email.upper()

@router.get("/public-crews", response_model=List[Crew])
async def get_public_crews():
    try:
        # Fetch crews from the 'crews' table
        crews_response = supabase.table('crews').select("*", count='exact').eq('is_public', True).execute()
        
        if not crews_response.data:
            return []
        
        result = []
        for crew in crews_response.data:
            creator_response = supabase.table('profiles').select('email').eq('id', crew['profile_id']).single().execute()
            agents_response = supabase.table('agents').select('*').eq('crew_id', crew['id']).execute()
            
            agents = []
            for agent in agents_response.data:
                tasks_response = supabase.table('tasks').select('*').eq('agent_id', agent['id']).execute()
                agent_with_tasks = {**agent, 'tasks': tasks_response.data or []}
                agents.append(agent_with_tasks)
            
            crew_response = {
                **crew,
                'creator_email': mask_email(creator_response.data.get('email', '')),
                'agents': agents
            }
            result.append(crew_response)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching public crews: {str(e)}")