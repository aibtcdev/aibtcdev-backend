from fastapi import APIRouter, HTTPException, Body, Depends
from services.crew_services import execute_crew
from .verify_profile import verify_profile

router = APIRouter()

@router.post("/execute_crew/{crew_id}")
async def execute_crew_endpoint(
    crew_id: int,
    input_str: str = Body(...),
    account_index: int = Depends(verify_profile)
):
    try:
        # Execute the crew logic with the provided input string
        result = await execute_crew(crew_id, input_str)
        
        return {"result": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
