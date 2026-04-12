import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings"""
    
    # Splunk
    SPLUNK_HOST: str = os.getenv("SPLUNK_HOST", "")
    SPLUNK_TOKEN: str = os.getenv("SPLUNK_TOKEN", "")
    
    # MongoDB
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB: str = "splunk_intelligence"
    
    # API
    API_PORT: int = int(os.getenv("API_PORT", 8080))
    
    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

settings = Settings()