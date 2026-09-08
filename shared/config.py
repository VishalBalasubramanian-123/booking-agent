# Env var loading (Supabase URL/key, AWS region, etc.).
import os
from dotenv import load_dotenv

load_dotenv()

TOOLS_LAMBDA_NAME = os.environ["TOOLS_LAMBDA_NAME"]
