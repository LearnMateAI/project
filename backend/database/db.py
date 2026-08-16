import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv
from gridfs import GridFS

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set. Check your backend/.env file.")

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client["learnmateai"]
documents_collection = db["documents"]
chunks_collection = db["chunks"]
resources_collection = db["resources"]
fs = GridFS(db)
def check_connection():
    """Quick check used at startup to confirm Mongo Atlas is reachable."""
    try:
        client.admin.command("ping")
        return True
    except Exception as e:
        print(f"[db.py] MongoDB connection failed: {e}")
        return False

users_collection = db["users"]
users_collection.create_index("email", unique=True)