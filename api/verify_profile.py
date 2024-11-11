from fastapi import Header, HTTPException, Depends
from dotenv import load_dotenv
from db.supabase_client import supabase
from pydantic import BaseModel

load_dotenv()


class ProfileInfo(BaseModel):
    account_index: int
    id: str


async def verify_profile(authorization: str = Header(...)) -> str:
    """
    Get and verify the account_index from the profile of the requesting user.
    Returns the account_index if valid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        print("Authorization header is missing or invalid.")
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )

    token = authorization.split(" ")[1]
    print(f"Authorization token received: {token}")

    try:
        # Get user email from the token
        user = supabase.auth.get_user(token)
        email = user.user.email

        # Retrieve the profile
        profile_response = (
            supabase.table("profiles")
            .select("account_index, email")
            .eq("email", email)
            .single()
            .execute()
        )

        if profile_response.data is None:
            print("Profile not found or retrieval failed in Supabase.")
            raise HTTPException(status_code=404, detail="Profile not found")

        profile = profile_response.data
        print(f"Profile data retrieved: {profile}")

        account_index = profile.get("account_index")
        if account_index is None:
            print("Account index is missing from profile data.")
            raise HTTPException(
                status_code=400, detail="No account index found for profile"
            )

        print(f"Account index for user is {account_index}")
        return ProfileInfo(account_index=str(account_index), id=user.user.id)

    except HTTPException as http_ex:
        print(f"HTTPException: {http_ex.detail}")
        raise http_ex  # Propagate HTTPException as-is

    except Exception as e:
        print("Authorization failed due to unexpected error.")
        print(f"Error details: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Authorization failed: {str(e)}")
