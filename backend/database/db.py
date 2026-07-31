import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set. Check your backend/.env file.")

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client["learnmateai"]

def check_connection():
    """Quick check used at startup to confirm Mongo Atlas is reachable."""
    try:
        client.admin.command("ping")
        return True
    except Exception as e:
        print(f"[db.py] MongoDB connection failed: {e}")
        return False
