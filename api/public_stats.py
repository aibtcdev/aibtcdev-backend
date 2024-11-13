# api/public_stats.py
from fastapi import APIRouter, HTTPException
from typing import List
import httpx
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(
    prefix="/public_stats",
    tags=["public_stats"]
)

class StatsResponse(BaseModel):
    timestamp: datetime
    total_jobs: int
    main_chat_jobs: int
    individual_crew_jobs: int
    top_profile_stacks_addresses: List[str]
    top_crew_names: List[str]

STATS_URL = "https://cache.aibtc.dev/supabase/stats"

@router.get("/", response_model=StatsResponse)
async def get_public_stats():
    """
    Fetch public statistics from the external API.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(STATS_URL, timeout=10.0)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"External API returned status code {response.status_code}"
                )
            
            return StatsResponse(**response.json())
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to external API: {str(e)}"
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Invalid response from external API: {str(e)}"
        )