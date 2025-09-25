import os

class Config:
    PORT = 8008
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-notifications-key")

    # Redis Configuration for message queue
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1") # Using DB 1 for notifications queue

    # Email settings (example, replace with actual credentials)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.example.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "your_email@example.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your_email_password")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@naebak.com")

    # SMS settings (example, integrate with a real SMS gateway like Twilio)
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

    # Push Notification settings (example, integrate with FCM or similar)
    FCM_SERVER_KEY = os.environ.get("FCM_SERVER_KEY")

    # CORS settings
    CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(",")

class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = "development"

class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = "production"

def get_config():
    if os.environ.get("FLASK_ENV") == "production":
        return ProductionConfig
    return DevelopmentConfig

