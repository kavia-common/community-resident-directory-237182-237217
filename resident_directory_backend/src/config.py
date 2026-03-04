"""
Configuration module for the Resident Directory Backend.
Loads settings from environment variables.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""
    
    # Database settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "appuser")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "dbuser123")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "myapp")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5000")
    
    # Construct database URL
    DATABASE_URL: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{POSTGRES_PORT}/{POSTGRES_DB}"
    
    # JWT settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-min-32-chars-recommended")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = os.getenv(
        "ALLOWED_ORIGINS", 
        "https://vscode-internal-13987-qa.qa01.cloud.kavia.ai:3000,http://localhost:3000"
    ).split(",")
    
    # Application settings
    PORT: int = int(os.getenv("PORT", "3001"))
    HOST: str = os.getenv("HOST", "0.0.0.0")


settings = Settings()
