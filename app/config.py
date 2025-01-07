from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    groq_api_key: str
    
    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

settings = Settings()
