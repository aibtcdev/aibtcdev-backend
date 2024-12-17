import os
from dotenv import load_dotenv
from supabase import create_client, Client
from lib.services import ServicesClient

# Load environment variables from .env file
load_dotenv()

# Initialize Supabase client using environment variables
url = os.getenv("SUPABASE_URL")
service_key = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, service_key)

services_client = ServicesClient(
    base_url=os.getenv("SERVICES_BASE_URL"),
    shared_key=os.getenv("SERVICES_SHARED_KEY")
)