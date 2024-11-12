from fastapi import APIRouter, HTTPException
from typing import List, Dict
from pydantic import BaseModel
from db.supabase_client import supabase

# Define the router for this module
router = APIRouter()

# Response model for crews by date
class CrewsByDateResponse(BaseModel):
    total_crews: int
    crews_by_date: Dict[str, List[str]]  # list crews based on their created dates

@router.get("/crews_metrics", response_model=CrewsByDateResponse)
async def get_crews():
    try:
        # Fetch only required fields from the crews table
        response = supabase.table('crews') \
            .select("name, created_at", count='exact') \
            .execute()
        
        if not response.data:
            return CrewsByDateResponse(
                total_crews=0,
                crews_by_date={}
            )
        
        # Calculate crews by date with their names
        crews_by_date = {}
        for crew in response.data:
            date_str = crew['created_at'].split('T')[0]  # Get YYYY-MM-DD part
            if date_str not in crews_by_date:
                crews_by_date[date_str] = []
            crews_by_date[date_str].append(crew['name'])
        
        return CrewsByDateResponse(
            total_crews=response.count if response.count is not None else len(response.data),
            crews_by_date=crews_by_date
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching crews: {str(e)}"
        )