from fastapi import Header, HTTPException, Depends
from dotenv import load_dotenv
from db.supabase_client import supabase
from pydantic import BaseModel
import datetime
import cachetools

load_dotenv()

cache = cachetools.TTLCache(maxsize=100, ttl=300)


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
    print(datetime.datetime.now())
    print(f"Authorization token received: {token}")

    try:
        # Get user email from the token
        print(datetime.datetime.now())
        user = supabase.auth.get_user(token)
        email = user.user.email
        print(datetime.datetime.now())

        # Check if the account_index is in the cache
        if email in cache:
            print(f"Cache hit for email: {email}")
            account_index = cache[email]
        else:
            print(f"Cache miss for email: {email}")
            # Retrieve the profile from Supabase
            profile_response = (
                supabase.table("profiles")
                .select("account_index, email")
                .eq("email", email)
                .single()
                .execute()
            )
            print(datetime.datetime.now())

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

            # Store the account_index in the cache
            cache[email] = account_index

        print(f"Account index for user is {account_index}")
        return ProfileInfo(account_index=str(account_index), id=user.user.id)

    except HTTPException as http_ex:
        print(f"HTTPException: {http_ex.detail}")
        raise http_ex  # Propagate HTTPException as-is

    except Exception as e:
        print("Authorization failed due to unexpected error.")
        print(f"Error details: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Authorization failed: {str(e)}")
