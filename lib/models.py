from pydantic import BaseModel
from typing import List


class ProfileInfo(BaseModel):
    account_index: int
    id: str

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
