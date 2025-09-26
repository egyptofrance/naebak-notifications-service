import os
from dataclasses import dataclass

@dataclass
class Config:
    PORT: int = int(os.getenv('PORT', 8003))
    HOST: str = os.getenv('HOST', '0.0.0.0')
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'postgresql://naebak_user:secure_password@localhost:5432/naebak_notifications')
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

def get_config():
    return Config()
