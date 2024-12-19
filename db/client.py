import os
from dotenv import load_dotenv
from lib.services import ServicesClient
from supabase import Client, create_client

# Load environment variables from .env file
load_dotenv()

# Initialize Supabase client using environment variables
url = os.getenv("AIBTC_SUPABASE_URL")
service_key = os.getenv("AIBTC_SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, service_key)

services_client = ServicesClient(
    base_url=os.getenv("SERVICES_BASE_URL"), shared_key=os.getenv("SERVICES_SHARED_KEY")
)
