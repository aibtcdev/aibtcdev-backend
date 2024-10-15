from fastapi import APIRouter, HTTPException, Body
from backend.services.crew_services import execute_crew

router = APIRouter()

@router.post("/execute_crew/{crew_id}")
async def execute_crew_endpoint(crew_id: int, input_str: str = Body(...)):
    try:
        # Execute the crew with the provided input and fetch the result
        result = execute_crew(crew_id, input_str)
        
        # Return the result without storing it in the database
        return {"result": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))