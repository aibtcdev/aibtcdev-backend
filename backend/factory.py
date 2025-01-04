import os
from .abstract import AbstractBackend
from .cloudflare import CloudflareBackend
from .supabase import SupabaseBackend
from dotenv import load_dotenv
from lib.services import ServicesClient
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from supabase import Client, create_client

load_dotenv()


def get_backend() -> AbstractBackend:
    """
    Factory function to get the appropriate backend implementation
    based on the AIBTC_BACKEND environment variable.
    """
    backend = os.getenv("AIBTC_BACKEND", "supabase")
    if backend == "supabase":

        USER = os.getenv("AIBTC_SUPABASE_USER")
        PASSWORD = os.getenv("AIBTC_SUPABASE_PASSWORD")
        HOST = os.getenv("AIBTC_SUPABASE_HOST")
        PORT = os.getenv("AIBTC_SUPABASE_PORT")
        DBNAME = os.getenv("AIBTC_SUPABASE_DBNAME")
        DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
        engine = create_engine(DATABASE_URL, poolclass=NullPool)

        URL = os.getenv("AIBTC_SUPABASE_URL")
        SERVICE_KEY = os.getenv("AIBTC_SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(URL, SERVICE_KEY)

        return SupabaseBackend(
            supabase,
            sqlalchemy_engine=engine,
            bucket_name=os.getenv("AIBTC_SUPABASE_BUCKET_NAME"),
        )
    services_url = os.getenv("AIBTC_SERVICES_BASE_URL")
    services_shared_key = os.getenv("AIBTC_SERVICES_SHARED_KEY")
    services_client: ServicesClient = ServicesClient(
        base_url=services_url, shared_key=services_shared_key
    )
    return CloudflareBackend(services_client)


# Create an instance
backend = get_backend()
