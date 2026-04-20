from dotenv import load_dotenv
import os

# Explicitly load .env from same directory as config.py
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 60))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

UPLOAD_DIR = "uploads/results"
os.makedirs(UPLOAD_DIR, exist_ok=True)