#!/usr/bin/env python3
"""
Naebak Notifications Service - Constants
========================================

Central constants and configuration values for the notifications service.
Contains all static values, enums, and configuration constants used
throughout the notification system.
"""

from enum import Enum
from typing import Dict, List, Tuple

# =============================================================================
# SERVICE CONFIGURATION
# =============================================================================

SERVICE_NAME = "naebak-notifications-service"
SERVICE_VERSION = "1.0.0"
API_VERSION = "v1"

# Default ports
DEFAULT_PORT = 5007
HEALTH_CHECK_PORT = 5008

# =============================================================================
# NOTIFICATION TYPES
# =============================================================================

class NotificationType(Enum):
    """Types of notifications"""
    WELCOME = "welcome"
    COMPLAINT_SUBMITTED = "complaint_submitted"
    COMPLAINT_UPDATED = "complaint_updated"
    COMPLAINT_RESOLVED = "complaint_resolved"
    MESSAGE_RECEIVED = "message_received"
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    REMINDER = "reminder"
    SECURITY_ALERT = "security_alert"
    ACCOUNT_UPDATE = "account_update"
    RATING_REQUEST = "rating_request"
    NEWSLETTER = "newsletter"
    MAINTENANCE = "maintenance"

# =============================================================================
# DELIVERY CHANNELS
# =============================================================================

class DeliveryChannel(Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"

# Channel priorities (higher number = higher priority)
CHANNEL_PRIORITIES = {
    DeliveryChannel.IN_APP: 1,
    DeliveryChannel.PUSH: 2,
    DeliveryChannel.EMAIL: 3,
    DeliveryChannel.SMS: 4,
    DeliveryChannel.WEBHOOK: 5
}

# =============================================================================
# NOTIFICATION PRIORITIES
# =============================================================================

class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

# Priority processing delays (in seconds)
PRIORITY_DELAYS = {
    NotificationPriority.CRITICAL: 0,      # Immediate
    NotificationPriority.URGENT: 5,       # 5 seconds
    NotificationPriority.HIGH: 30,        # 30 seconds
    NotificationPriority.NORMAL: 60,      # 1 minute
    NotificationPriority.LOW: 300         # 5 minutes
}

# =============================================================================
# DELIVERY STATUS
# =============================================================================

class DeliveryStatus(Enum):
    """Delivery status values"""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

# Final statuses (no further processing)
FINAL_STATUSES = {
    DeliveryStatus.DELIVERED,
    DeliveryStatus.READ,
    DeliveryStatus.FAILED,
    DeliveryStatus.BOUNCED,
    DeliveryStatus.REJECTED,
    DeliveryStatus.EXPIRED,
    DeliveryStatus.CANCELLED
}

# =============================================================================
# ERROR TYPES
# =============================================================================

class ErrorType(Enum):
    """Error types for failed notifications"""
    INVALID_RECIPIENT = "invalid_recipient"
    NETWORK_ERROR = "network_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    CONTENT_REJECTED = "content_rejected"
    RECIPIENT_BLOCKED = "recipient_blocked"
    QUOTA_EXCEEDED = "quota_exceeded"
    TIMEOUT = "timeout"
    INVALID_TEMPLATE = "invalid_template"
    MISSING_CREDENTIALS = "missing_credentials"
    UNKNOWN = "unknown"

# Retryable error types
RETRYABLE_ERRORS = {
    ErrorType.NETWORK_ERROR,
    ErrorType.SERVICE_UNAVAILABLE,
    ErrorType.RATE_LIMITED,
    ErrorType.TIMEOUT,
    ErrorType.QUOTA_EXCEEDED
}

# =============================================================================
# TEMPLATE TYPES
# =============================================================================

class TemplateType(Enum):
    """Template types"""
    HTML = "html"
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"

# =============================================================================
# USER PREFERENCES
# =============================================================================

class UserPreference(Enum):
    """User notification preferences"""
    ALL = "all"
    IMPORTANT_ONLY = "important_only"
    NONE = "none"
    CUSTOM = "custom"

# Default user preferences by channel
DEFAULT_USER_PREFERENCES = {
    DeliveryChannel.EMAIL: UserPreference.ALL,
    DeliveryChannel.SMS: UserPreference.IMPORTANT_ONLY,
    DeliveryChannel.PUSH: UserPreference.ALL,
    DeliveryChannel.IN_APP: UserPreference.ALL,
    DeliveryChannel.WEBHOOK: UserPreference.NONE
}

# =============================================================================
# RATE LIMITING
# =============================================================================

# Rate limits per channel (requests per minute)
RATE_LIMITS = {
    DeliveryChannel.EMAIL: 100,
    DeliveryChannel.SMS: 50,
    DeliveryChannel.PUSH: 1000,
    DeliveryChannel.IN_APP: 2000,
    DeliveryChannel.WEBHOOK: 200
}

# Burst limits (maximum requests in burst)
BURST_LIMITS = {
    DeliveryChannel.EMAIL: 20,
    DeliveryChannel.SMS: 10,
    DeliveryChannel.PUSH: 100,
    DeliveryChannel.IN_APP: 200,
    DeliveryChannel.WEBHOOK: 50
}

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================

# Maximum retry attempts per channel
MAX_RETRIES = {
    DeliveryChannel.EMAIL: 3,
    DeliveryChannel.SMS: 2,
    DeliveryChannel.PUSH: 3,
    DeliveryChannel.IN_APP: 1,
    DeliveryChannel.WEBHOOK: 5
}

# Retry delays (in seconds) - exponential backoff
RETRY_DELAYS = [60, 300, 900, 1800, 3600]  # 1min, 5min, 15min, 30min, 1hr

# Maximum age for retries (in hours)
MAX_RETRY_AGE = 24

# =============================================================================
# EXTERNAL SERVICES
# =============================================================================

# Email service providers
class EmailProvider(Enum):
    """Email service providers"""
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    SES = "ses"
    SMTP = "smtp"

# SMS service providers
class SMSProvider(Enum):
    """SMS service providers"""
    TWILIO = "twilio"
    NEXMO = "nexmo"
    MESSAGEBIRD = "messagebird"
    LOCAL = "local"

# Push notification services
class PushProvider(Enum):
    """Push notification providers"""
    FCM = "fcm"
    APNS = "apns"
    WNS = "wns"

# =============================================================================
# TEMPLATE DEFAULTS
# =============================================================================

# Default templates for each notification type
DEFAULT_TEMPLATES = {
    NotificationType.WELCOME: {
        DeliveryChannel.EMAIL: "welcome_email",
        DeliveryChannel.SMS: "welcome_sms",
        DeliveryChannel.PUSH: "welcome_push",
        DeliveryChannel.IN_APP: "welcome_in_app"
    },
    NotificationType.COMPLAINT_SUBMITTED: {
        DeliveryChannel.EMAIL: "complaint_submitted_email",
        DeliveryChannel.SMS: "complaint_submitted_sms",
        DeliveryChannel.PUSH: "complaint_submitted_push",
        DeliveryChannel.IN_APP: "complaint_submitted_in_app"
    },
    NotificationType.COMPLAINT_UPDATED: {
        DeliveryChannel.EMAIL: "complaint_updated_email",
        DeliveryChannel.SMS: "complaint_updated_sms",
        DeliveryChannel.PUSH: "complaint_updated_push",
        DeliveryChannel.IN_APP: "complaint_updated_in_app"
    },
    NotificationType.MESSAGE_RECEIVED: {
        DeliveryChannel.EMAIL: "message_received_email",
        DeliveryChannel.SMS: "message_received_sms",
        DeliveryChannel.PUSH: "message_received_push",
        DeliveryChannel.IN_APP: "message_received_in_app"
    }
}

# =============================================================================
# LOCALIZATION
# =============================================================================

# Supported languages
SUPPORTED_LANGUAGES = ["ar", "en"]
DEFAULT_LANGUAGE = "ar"

# RTL languages
RTL_LANGUAGES = ["ar", "he", "fa"]

# =============================================================================
# VALIDATION RULES
# =============================================================================

# Email validation
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Phone number validation (Egyptian format)
PHONE_REGEX = r'^(\+20|0)?1[0-9]{9}$'

# Maximum content lengths
MAX_CONTENT_LENGTHS = {
    DeliveryChannel.EMAIL: {
        'subject': 200,
        'body': 50000
    },
    DeliveryChannel.SMS: {
        'body': 160
    },
    DeliveryChannel.PUSH: {
        'title': 50,
        'body': 200
    },
    DeliveryChannel.IN_APP: {
        'title': 100,
        'body': 1000
    }
}

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

# Token expiration times (in seconds)
TOKEN_EXPIRATION = {
    'access_token': 3600,      # 1 hour
    'refresh_token': 86400,    # 24 hours
    'webhook_token': 300       # 5 minutes
}

# Encryption settings
ENCRYPTION_ALGORITHM = "AES-256-GCM"
HASH_ALGORITHM = "SHA-256"

# =============================================================================
# MONITORING AND LOGGING
# =============================================================================

# Log levels
LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50
}

# Metrics collection intervals (in seconds)
METRICS_INTERVALS = {
    'real_time': 10,
    'minute': 60,
    'hour': 3600,
    'daily': 86400
}

# Health check endpoints
HEALTH_CHECK_ENDPOINTS = [
    '/health',
    '/health/ready',
    '/health/live'
]

# =============================================================================
# CACHE SETTINGS
# =============================================================================

# Cache TTL values (in seconds)
CACHE_TTL = {
    'user_preferences': 3600,      # 1 hour
    'templates': 1800,             # 30 minutes
    'delivery_status': 300,        # 5 minutes
    'rate_limits': 60,             # 1 minute
    'analytics': 300               # 5 minutes
}

# Cache key prefixes
CACHE_PREFIXES = {
    'user_pref': 'user_pref:',
    'template': 'template:',
    'delivery': 'delivery:',
    'rate_limit': 'rate_limit:',
    'analytics': 'analytics:'
}

# =============================================================================
# QUEUE SETTINGS
# =============================================================================

# Queue names
QUEUE_NAMES = {
    'high_priority': 'notifications_high',
    'normal_priority': 'notifications_normal',
    'low_priority': 'notifications_low',
    'retry': 'notifications_retry',
    'dead_letter': 'notifications_dlq'
}

# Queue processing settings
QUEUE_SETTINGS = {
    'batch_size': 10,
    'visibility_timeout': 300,     # 5 minutes
    'message_retention': 1209600,  # 14 days
    'max_receives': 3
}

# =============================================================================
# API SETTINGS
# =============================================================================

# API rate limits (requests per minute)
API_RATE_LIMITS = {
    'send_notification': 1000,
    'get_status': 2000,
    'get_analytics': 100,
    'manage_templates': 50
}

# API response codes
API_RESPONSE_CODES = {
    'SUCCESS': 200,
    'CREATED': 201,
    'ACCEPTED': 202,
    'BAD_REQUEST': 400,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'NOT_FOUND': 404,
    'RATE_LIMITED': 429,
    'INTERNAL_ERROR': 500,
    'SERVICE_UNAVAILABLE': 503
}

# =============================================================================
# DATABASE SETTINGS
# =============================================================================

# Table names
TABLE_NAMES = {
    'notifications': 'notifications',
    'delivery_records': 'delivery_records',
    'user_preferences': 'user_preferences',
    'templates': 'notification_templates',
    'analytics': 'notification_analytics'
}

# Index names
INDEX_NAMES = {
    'user_id_idx': 'idx_notifications_user_id',
    'status_idx': 'idx_delivery_status',
    'created_at_idx': 'idx_notifications_created_at',
    'channel_idx': 'idx_delivery_channel'
}

# =============================================================================
# WEBHOOK SETTINGS
# =============================================================================

# Webhook events
class WebhookEvent(Enum):
    """Webhook event types"""
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_DELIVERED = "notification.delivered"
    NOTIFICATION_READ = "notification.read"
    NOTIFICATION_FAILED = "notification.failed"
    DELIVERY_STATUS_CHANGED = "delivery.status_changed"

# Webhook retry settings
WEBHOOK_RETRY_ATTEMPTS = 3
WEBHOOK_TIMEOUT = 30  # seconds
WEBHOOK_RETRY_DELAYS = [5, 15, 60]  # seconds

# =============================================================================
# FEATURE FLAGS
# =============================================================================

# Feature flags for enabling/disabling functionality
FEATURE_FLAGS = {
    'enable_sms': True,
    'enable_push': True,
    'enable_webhooks': True,
    'enable_analytics': True,
    'enable_rate_limiting': True,
    'enable_retry_mechanism': True,
    'enable_template_caching': True,
    'enable_user_preferences': True,
    'enable_delivery_tracking': True,
    'enable_real_time_metrics': True
}

# =============================================================================
# ENVIRONMENT SPECIFIC SETTINGS
# =============================================================================

# Development settings
DEV_SETTINGS = {
    'debug': True,
    'log_level': 'DEBUG',
    'rate_limiting_enabled': False,
    'mock_external_services': True
}

# Production settings
PROD_SETTINGS = {
    'debug': False,
    'log_level': 'INFO',
    'rate_limiting_enabled': True,
    'mock_external_services': False
}

# =============================================================================
# ARABIC LANGUAGE CONSTANTS
# =============================================================================

# Arabic text constants
ARABIC_TEXTS = {
    'welcome_title': 'مرحباً بك في منصة نائبك',
    'complaint_submitted': 'تم تقديم شكواك بنجاح',
    'complaint_updated': 'تم تحديث حالة شكواك',
    'message_received': 'لديك رسالة جديدة',
    'system_announcement': 'إعلان من النظام',
    'security_alert': 'تنبيه أمني',
    'account_updated': 'تم تحديث حسابك',
    'rating_request': 'قيّم تجربتك معنا',
    'maintenance_notice': 'إشعار صيانة',
    'newsletter': 'النشرة الإخبارية'
}

# Status texts in Arabic
STATUS_TEXTS_AR = {
    DeliveryStatus.PENDING: 'في الانتظار',
    DeliveryStatus.QUEUED: 'في الطابور',
    DeliveryStatus.SENDING: 'جاري الإرسال',
    DeliveryStatus.SENT: 'تم الإرسال',
    DeliveryStatus.DELIVERED: 'تم التسليم',
    DeliveryStatus.READ: 'تم القراءة',
    DeliveryStatus.FAILED: 'فشل',
    DeliveryStatus.BOUNCED: 'مرتد',
    DeliveryStatus.REJECTED: 'مرفوض',
    DeliveryStatus.EXPIRED: 'منتهي الصلاحية',
    DeliveryStatus.CANCELLED: 'ملغي'
}

# Channel names in Arabic
CHANNEL_NAMES_AR = {
    DeliveryChannel.EMAIL: 'البريد الإلكتروني',
    DeliveryChannel.SMS: 'الرسائل النصية',
    DeliveryChannel.PUSH: 'الإشعارات الفورية',
    DeliveryChannel.IN_APP: 'داخل التطبيق',
    DeliveryChannel.WEBHOOK: 'الويب هوك'
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_channel_priority(channel: DeliveryChannel) -> int:
    """Get priority for a delivery channel"""
    return CHANNEL_PRIORITIES.get(channel, 0)

def get_max_retries(channel: DeliveryChannel) -> int:
    """Get maximum retries for a channel"""
    return MAX_RETRIES.get(channel, 3)

def get_rate_limit(channel: DeliveryChannel) -> int:
    """Get rate limit for a channel"""
    return RATE_LIMITS.get(channel, 100)

def is_retryable_error(error_type: ErrorType) -> bool:
    """Check if error type is retryable"""
    return error_type in RETRYABLE_ERRORS

def is_final_status(status: DeliveryStatus) -> bool:
    """Check if status is final (no further processing)"""
    return status in FINAL_STATUSES

def get_retry_delay(attempt: int) -> int:
    """Get retry delay for attempt number"""
    if attempt <= 0:
        return 0
    index = min(attempt - 1, len(RETRY_DELAYS) - 1)
    return RETRY_DELAYS[index]

def get_default_template(notification_type: NotificationType, 
                        channel: DeliveryChannel) -> str:
    """Get default template for notification type and channel"""
    return DEFAULT_TEMPLATES.get(notification_type, {}).get(channel, 'default')

def get_max_content_length(channel: DeliveryChannel, content_type: str) -> int:
    """Get maximum content length for channel and content type"""
    return MAX_CONTENT_LENGTHS.get(channel, {}).get(content_type, 1000)

def get_arabic_status_text(status: DeliveryStatus) -> str:
    """Get Arabic text for delivery status"""
    return STATUS_TEXTS_AR.get(status, status.value)

def get_arabic_channel_name(channel: DeliveryChannel) -> str:
    """Get Arabic name for delivery channel"""
    return CHANNEL_NAMES_AR.get(channel, channel.value)

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_email(email: str) -> bool:
    """Validate email address format"""
    import re
    return bool(re.match(EMAIL_REGEX, email))

def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    import re
    return bool(re.match(PHONE_REGEX, phone))

def validate_content_length(content: str, channel: DeliveryChannel, 
                          content_type: str) -> bool:
    """Validate content length for channel"""
    max_length = get_max_content_length(channel, content_type)
    return len(content) <= max_length

# =============================================================================
# EXPORT ALL CONSTANTS
# =============================================================================

__all__ = [
    # Service info
    'SERVICE_NAME', 'SERVICE_VERSION', 'API_VERSION',
    'DEFAULT_PORT', 'HEALTH_CHECK_PORT',
    
    # Enums
    'NotificationType', 'DeliveryChannel', 'NotificationPriority',
    'DeliveryStatus', 'ErrorType', 'TemplateType', 'UserPreference',
    'EmailProvider', 'SMSProvider', 'PushProvider', 'WebhookEvent',
    
    # Configuration dictionaries
    'CHANNEL_PRIORITIES', 'PRIORITY_DELAYS', 'FINAL_STATUSES',
    'RETRYABLE_ERRORS', 'DEFAULT_USER_PREFERENCES', 'RATE_LIMITS',
    'BURST_LIMITS', 'MAX_RETRIES', 'RETRY_DELAYS', 'DEFAULT_TEMPLATES',
    'MAX_CONTENT_LENGTHS', 'TOKEN_EXPIRATION', 'CACHE_TTL',
    'QUEUE_NAMES', 'API_RATE_LIMITS', 'FEATURE_FLAGS',
    
    # Text constants
    'ARABIC_TEXTS', 'STATUS_TEXTS_AR', 'CHANNEL_NAMES_AR',
    
    # Utility functions
    'get_channel_priority', 'get_max_retries', 'get_rate_limit',
    'is_retryable_error', 'is_final_status', 'get_retry_delay',
    'get_default_template', 'get_max_content_length',
    'get_arabic_status_text', 'get_arabic_channel_name',
    
    # Validation functions
    'validate_email', 'validate_phone', 'validate_content_length'
]
