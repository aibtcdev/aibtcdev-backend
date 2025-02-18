from backend.abstract import AbstractBackend
from backend.supabase import SupabaseBackend
from config import config
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from supabase import Client, create_client


def get_backend() -> AbstractBackend:
    """Get the backend implementation based on configuration."""
    if config.db.backend == "supabase":
        return _get_supabase_backend()
    else:
        raise ValueError(f"Unsupported backend: {config.db.backend}")


def _get_supabase_backend() -> SupabaseBackend:
    """Get a Supabase backend implementation."""
    client: Client = create_client(config.db.url, config.db.service_key)
    DATABASE_URL = f"postgresql+psycopg2://{config.db.user}:{config.db.password}@{config.db.host}:{config.db.port}/{config.db.dbname}?sslmode=require"
    engine = create_engine(DATABASE_URL, poolclass=NullPool)
    return SupabaseBackend(
        client=client,
        sqlalchemy_engine=engine,
        bucket_name=config.db.bucket_name,
    )


# Create an instance
backend = get_backend()
