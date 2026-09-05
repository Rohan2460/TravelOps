import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "External Data API Simulator"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    DB_FILE: str = os.path.join(DATA_DIR, "simulator_db.json")

settings = Settings()
