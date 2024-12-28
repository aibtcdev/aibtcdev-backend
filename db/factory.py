import os
from .cloudflare_db import CloudflareDatabase
from .database import Database
from .supabase_db import SupabaseDatabase
from dotenv import load_dotenv
from lib.services import ServicesClient
from supabase import Client, create_client

load_dotenv()


def get_database() -> Database:
    """
    Factory function to get the appropriate database implementation
    based on the AIBTC_BACKEND environment variable.
    """
    backend = os.getenv("AIBTC_BACKEND", "supabase")
    if backend == "supabase":
        url = os.getenv("AIBTC_SUPABASE_URL")
        service_key = os.getenv("AIBTC_SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(url, service_key)
        return SupabaseDatabase(
            supabase, bucket_name=os.getenv("AIBTC_SUPABASE_BUCKET_NAME")
        )
    services_url = os.getenv("AIBTC_SERVICES_BASE_URL")
    services_shared_key = os.getenv("AIBTC_SERVICES_SHARED_KEY")
    services_client: ServicesClient = ServicesClient(
        base_url=services_url, shared_key=services_shared_key
    )
    return CloudflareDatabase(services_client)


# Create a singleton instance
db = get_database()
