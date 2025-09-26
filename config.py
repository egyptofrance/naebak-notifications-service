"""
Configuration module for Naebak Notifications Service.

This module provides configuration management for the notifications service,
including database connections, external service credentials, and application
settings. It supports multiple environments (development, staging, production)
and loads configuration from environment variables.
"""

import os
from typing import List


class Config:
    """Base configuration class with common settings."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-notifications-key')
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
    TESTING = False
    
    # Server settings
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 8008))
    
    # Database settings
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://naebak_user:naebak_password@localhost:5432/naebak_notifications'
    )
    
    # Redis settings
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    
    # CORS settings
    ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(",")
    
    # Celery settings
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/2')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/3')
    
    # Email settings (SendGrid)
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    FROM_EMAIL = os.environ.get('FROM_EMAIL', 'noreply@naebak.com')
    FROM_NAME = os.environ.get('FROM_NAME', 'منصة نائبك')
    REPLY_TO_EMAIL = os.environ.get('REPLY_TO_EMAIL', 'support@naebak.com')
    
    # Legacy email settings (backward compatibility)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.example.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "your_email@example.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your_email_password")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@naebak.com")
    
    # SMS settings (Twilio)
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
    TWILIO_WEBHOOK_URL = os.environ.get('TWILIO_WEBHOOK_URL')
    
    # Push notification settings (Firebase Cloud Messaging)
    FCM_API_KEY = os.environ.get("FCM_SERVER_KEY")
    FCM_PROJECT_ID = os.environ.get('FCM_PROJECT_ID')
    FCM_DEFAULT_ICON = os.environ.get('FCM_DEFAULT_ICON', '/static/icons/notification.png')
    FCM_DEFAULT_SOUND = os.environ.get('FCM_DEFAULT_SOUND', 'default')
    
    # WebSocket settings
    WEBSOCKET_URL = os.environ.get('WEBSOCKET_URL', 'ws://localhost:8000')
    
    # Rate limiting settings
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', 60))
    RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', 1000))
    
    # Notification settings
    MAX_RETRY_ATTEMPTS = int(os.environ.get('MAX_RETRY_ATTEMPTS', 3))
    RETRY_DELAY_SECONDS = int(os.environ.get('RETRY_DELAY_SECONDS', 300))
    BATCH_SIZE = int(os.environ.get('BATCH_SIZE', 100))
    
    # Template settings
    TEMPLATE_CACHE_TTL = int(os.environ.get('TEMPLATE_CACHE_TTL', 3600))
    DEFAULT_LANGUAGE = os.environ.get('DEFAULT_LANGUAGE', 'ar')
    SUPPORTED_LANGUAGES = os.environ.get('SUPPORTED_LANGUAGES', 'ar,en').split(',')


class DevelopmentConfig(Config):
    """Development environment configuration."""
    
    DEBUG = True
    FLASK_ENV = "development"
    
    # Use local services for development
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://naebak_user:naebak_password@localhost:5432/naebak_notifications_dev'
    )
    
    # Relaxed CORS for development
    ALLOWED_ORIGINS = ['http://localhost:3000', 'http://localhost:8080', '*']
    
    # Lower rate limits for development
    RATE_LIMIT_PER_MINUTE = 120
    RATE_LIMIT_PER_HOUR = 2000


class TestingConfig(Config):
    """Testing environment configuration."""
    
    TESTING = True
    DEBUG = True
    FLASK_ENV = "testing"
    
    # Use in-memory database for testing
    DATABASE_URL = 'sqlite:///:memory:'
    
    # Use fake Redis for testing
    REDIS_URL = 'redis://localhost:6379/15'
    
    # Disable external services for testing
    SENDGRID_API_KEY = 'test-sendgrid-key'
    TWILIO_ACCOUNT_SID = 'test-twilio-sid'
    TWILIO_AUTH_TOKEN = 'test-twilio-token'
    FCM_API_KEY = 'test-fcm-key'
    
    # Higher rate limits for testing
    RATE_LIMIT_PER_MINUTE = 1000
    RATE_LIMIT_PER_HOUR = 10000


class ProductionConfig(Config):
    """Production environment configuration."""
    
    DEBUG = False
    FLASK_ENV = "production"
    
    # Strict CORS for production
    ALLOWED_ORIGINS = [
        'https://naebak.com',
        'https://www.naebak.com',
        'https://api.naebak.com'
    ]
    
    # Production database with connection pooling
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Production Redis with SSL
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # Strict rate limits for production
    RATE_LIMIT_PER_MINUTE = 30
    RATE_LIMIT_PER_HOUR = 500


def get_config():
    """
    Get configuration based on environment.
    
    Returns:
        Config: Configuration object for current environment
    """
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()

