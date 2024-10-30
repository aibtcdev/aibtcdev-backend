from fastapi import APIRouter, HTTPException, Body, Query
from services.crew_services import execute_crew
from tools.bun import BunScriptRunner

router = APIRouter()


@router.post("/execute_crew/{crew_id}")
async def execute_crew_endpoint(
    crew_id: int,
    input_str: str = Body(...),
    address: str = Query(..., description="The address to be used"),
    signed_message: str = Query(..., description="The signed message to be used"),
):
    try:

        # Validate the signed_message with the address to ensure it was signed by the address
        valid = BunScriptRunner.bun_run(
            "0", "stacks-wallet", "verify.ts", signed_message, address
        )
        if valid["success"] is False:  # If the signed message is not valid
            raise HTTPException(status_code=400, detail="Invalid signed message")

        # Needs logic here to lookup the account_index by the address in the database
        # account_index = get_account_index_by_address(address)

        # Execute the crew with the provided input and fetch the result
        result = execute_crew(account_index, crew_id, input_str)

        # Return the result without storing it in the database
        return {"result": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
