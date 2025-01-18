import os
from .abstract import AbstractBackend
from .supabase import SupabaseBackend
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from supabase import Client, ClientOptions, create_client

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
        supabase_queue: Client = create_client(
            URL, SERVICE_KEY, ClientOptions(schema="pgmq_public")
        )

        return SupabaseBackend(
            supabase,
            supabase_queue,
            sqlalchemy_engine=engine,
            bucket_name=os.getenv("AIBTC_SUPABASE_BUCKET_NAME"),
        )


# Create an instance
backend = get_backend()
