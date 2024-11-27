from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from db.client import supabase
import httpx
import os
from lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Define the router for this module
router = APIRouter(prefix="/metrics")

# Response model for crews by date
class CrewsByDateResponse(BaseModel):
    total_crews: int
    crews_by_date: Dict[str, List[str]]  # list crews based on their created dates


class StatsResponse(BaseModel):
    timestamp: datetime
    total_jobs: int
    main_chat_jobs: int
    individual_crew_jobs: int
    top_profile_stacks_addresses: List[str]
    top_crew_names: List[str]

# Get STATS_URL from environment with default value
STATS_URL = os.getenv('STATS_URL', 'https://cache.aibtc.dev/supabase/stats')

@router.get("/public", response_model=StatsResponse)
async def get_public_stats():
    """
    Fetch public statistics from the external API.
    """
    try:
        logger.debug(f"Fetching public stats from {STATS_URL}")
        async with httpx.AsyncClient() as client:
            response = await client.get(STATS_URL, timeout=10.0)
            
            if response.status_code != 200:
                logger.error(f"External API returned non-200 status code: {response.status_code}")
                raise HTTPException(
                    status_code=502,
                    detail=f"External API returned status code {response.status_code}"
                )
            
            stats = StatsResponse(**response.json())
            logger.info("Successfully fetched public stats")
            return stats
            
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to external API: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to external API: {str(e)}"
        )
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid response from external API: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Invalid response from external API: {str(e)}"
        )

@router.get("/crews", response_model=CrewsByDateResponse)
async def get_crews():
    try:
        logger.debug("Fetching crews data from database")
        # Fetch only required fields from the crews table
        response = supabase.table('crews') \
            .select("id,created_at,name") \
            .execute()
            
        crews_data = response.data
        crews_by_date = {}
        
        # Group crews by date
        for crew in crews_data:
            date = crew['created_at'].split('T')[0]  # Get just the date part
            if date not in crews_by_date:
                crews_by_date[date] = []
            crews_by_date[date].append(crew['name'])
        
        result = CrewsByDateResponse(
            total_crews=len(crews_data),
            crews_by_date=crews_by_date
        )
        
        logger.info(f"Successfully fetched {len(crews_data)} crews")
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch crews data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch crews data: {str(e)}"
        )