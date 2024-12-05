from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from db.helpers import get_crews_metrics
import httpx
import os
from lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/metrics")

class CrewsByDateResponse(BaseModel):
    """Response model for crews grouped by creation date.
    
    Attributes:
        total_crews (int): Total number of crews in the system
        crews_by_date (Dict[str, List[str]]): Dictionary mapping dates to lists of crew names
    """
    total_crews: int
    crews_by_date: Dict[str, List[str]]

class StatsResponse(BaseModel):
    """Response model for system-wide statistics.
    
    Attributes:
        timestamp (datetime): When these statistics were generated
        total_jobs (int): Total number of jobs in the system
        main_chat_jobs (int): Number of jobs from main chat
        individual_crew_jobs (int): Number of jobs from individual crews
        top_profile_stacks_addresses (List[str]): Most active stack addresses
        top_crew_names (List[str]): Most used crew names
    """
    timestamp: datetime
    total_jobs: int
    main_chat_jobs: int
    individual_crew_jobs: int
    top_profile_stacks_addresses: List[str]
    top_crew_names: List[str]

# Get STATS_URL from environment with default value
STATS_URL = os.getenv('STATS_URL', 'https://cache.aibtc.dev/supabase/stats')

@router.get("/stats", response_model=StatsResponse)
async def get_public_stats() -> StatsResponse:
    """Fetch public statistics from the external API.
    
    Returns:
        StatsResponse: System-wide statistics including job counts and top users
        
    Raises:
        HTTPException: If the stats API is unreachable or returns invalid data
    """
    logger.debug("Fetching public statistics from external API")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(STATS_URL)
            response.raise_for_status()
            data = response.json()
            logger.debug("Successfully retrieved public statistics")
            return StatsResponse(
                timestamp=datetime.fromisoformat(data["timestamp"]),
                total_jobs=data["total_jobs"],
                main_chat_jobs=data["main_chat_jobs"],
                individual_crew_jobs=data["individual_crew_jobs"],
                top_profile_stacks_addresses=data["top_profile_stacks_addresses"],
                top_crew_names=data["top_crew_names"],
            )
    except httpx.HTTPError as e:
        logger.error(f"HTTP error while fetching public stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Stats API unavailable: {str(e)}"
        )
    except KeyError as e:
        logger.error(f"Invalid data format in stats response: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Invalid stats data format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching public stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching public stats: {str(e)}"
        )

@router.get("/crews", response_model=CrewsByDateResponse)
async def get_crews() -> CrewsByDateResponse:
    """Get all crews grouped by their creation date.
    
    Returns:
        CrewsByDateResponse: Total number of crews and crews grouped by date
        
    Raises:
        HTTPException: If there's an error fetching crews from the database
    """
    try:
        logger.debug("Fetching crews data from database")
        response = get_crews_metrics()
        crews_data = response.data
        crews_by_date: Dict[str, List[str]] = {}
        
        # Group crews by date
        for crew in crews_data:
            date = crew['created_at'].split('T')[0]  # Get just the date part
            if date not in crews_by_date:
                crews_by_date[date] = []
            crews_by_date[date].append(crew['name'])
        
        total_crews = len(crews_data)
        logger.debug(f"Successfully retrieved {total_crews} crews across {len(crews_by_date)} dates")
        
        result = CrewsByDateResponse(
            total_crews=total_crews,
            crews_by_date=crews_by_date
        )
        return result

    except Exception as e:
        logger.error(f"Error fetching crews data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching crews data: {str(e)}"
        )