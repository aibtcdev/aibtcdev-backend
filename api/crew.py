from fastapi import APIRouter, HTTPException, Body, Query
from services.crew_services import execute_crew

router = APIRouter()


@router.post("/execute_crew/{crew_id}")
async def execute_crew_endpoint(
    crew_id: int,
    account_index: str = Query(..., description="The account index to be used"),
    input_str: str = Body(...),
):
    try:
        # Execute the crew with the provided input and fetch the result
        result = execute_crew(account_index, crew_id, input_str)

        # Return the result without storing it in the database
        return {"result": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
