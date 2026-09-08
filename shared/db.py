# Supabase client/connection setup.
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ["SUPABASE_URL"]
key: str = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(url, key)


if __name__ == "__main__":
    response = supabase.table("session").select("*").execute()
    print(response)