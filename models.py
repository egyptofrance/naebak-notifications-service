"""
Naebak Notifications Service - Database Models

This module defines the SQLAlchemy models for the notifications service,
providing comprehensive data structures for managing notifications, templates,
user preferences, and delivery tracking across multiple channels.

The models are designed to support:
- Multi-channel notification delivery (email, SMS, push)
- Template-based notification content with variables
- User-specific notification preferences and settings
- Comprehensive delivery tracking and status monitoring
- Integration with the broader Naebak platform ecosystem
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class NotificationChannel(enum.Enum):
    """
    Enumeration of supported notification delivery channels.
    
    This enum defines the available channels for delivering notifications
    to users, each with specific characteristics and delivery mechanisms.
    
    Channels:
        EMAIL: Email notifications with HTML/text content support
        SMS: Short message service for mobile devices
        PUSH: Push notifications for mobile and web applications
        IN_APP: In-application notifications displayed within the platform
    """
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"

class NotificationType(enum.Enum):
    """
    Enumeration of notification types for categorization and processing.
    
    This enum categorizes notifications based on their purpose and content,
    enabling appropriate handling, prioritization, and user preference management.
    
    Types:
        WELCOME: User onboarding and welcome messages
        SECURITY: Security alerts and authentication notifications
        MESSAGE: Communication and messaging alerts
        COMPLAINT: Complaint status updates and responses
        ELECTION: Election alerts and political engagement notifications
        SYSTEM: System maintenance and platform updates
        REMINDER: Scheduled reminders and follow-ups
        MARKETING: Promotional and engagement content
    """
    WELCOME = "welcome"
    SECURITY = "security"
    MESSAGE = "message"
    COMPLAINT = "complaint"
    ELECTION = "election"
    SYSTEM = "system"
    REMINDER = "reminder"
    MARKETING = "marketing"

class NotificationStatus(enum.Enum):
    """
    Enumeration of notification delivery status states.
    
    This enum tracks the lifecycle of notification delivery from creation
    to final delivery confirmation or failure.
    
    States:
        PENDING: Notification created but not yet processed
        QUEUED: Notification added to delivery queue
        PROCESSING: Notification currently being processed
        SENT: Notification sent to delivery provider
        DELIVERED: Notification successfully delivered to recipient
        FAILED: Notification delivery failed
        CANCELLED: Notification cancelled before delivery
    """
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"

class NotificationPriority(enum.Enum):
    """
    Enumeration of notification priority levels for processing order.
    
    This enum defines priority levels that determine processing order
    and delivery urgency for notifications in the queue.
    
    Priorities:
        LOW: Non-urgent notifications (marketing, general updates)
        NORMAL: Standard notifications (messages, reminders)
        HIGH: Important notifications (security, complaints)
        URGENT: Critical notifications (system alerts, emergencies)
    """
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationTemplate(Base):
    """
    Model for storing notification templates with variable substitution.
    
    This model manages reusable notification templates that support
    variable substitution for personalized content across different
    channels and notification types.
    
    Attributes:
        id (UUID): Unique identifier for the template
        name (str): Human-readable template name
        notification_type (NotificationType): Type of notification this template serves
        channel (NotificationChannel): Target delivery channel
        subject (str): Subject line for email notifications (optional for other channels)
        content (str): Template content with variable placeholders
        variables (JSON): Schema defining available template variables
        is_active (bool): Whether the template is currently active
        created_at (datetime): Template creation timestamp
        updated_at (datetime): Last modification timestamp
        created_by (str): User ID of template creator
    
    Template Variables:
        Templates support Jinja2-style variable substitution with placeholders
        like {{user_name}}, {{complaint_id}}, etc. The variables field stores
        the schema defining available variables and their types.
    
    Example:
        A welcome email template might have:
        - subject: "مرحباً بك في منصة نائبك، {{user_name}}"
        - content: "عزيزي {{user_name}}، نرحب بك في منصة نائبك..."
        - variables: {"user_name": {"type": "string", "required": true}}
    """
    __tablename__ = 'notification_templates'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    subject = Column(String(500))  # For email notifications
    content = Column(Text, nullable=False)
    variables = Column(JSON)  # Schema for template variables
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(50))  # User ID who created the template
    
    # Relationships
    notifications = relationship("Notification", back_populates="template")
    
    def __repr__(self):
        return f"<NotificationTemplate(name='{self.name}', type='{self.notification_type.value}', channel='{self.channel.value}')>"

class UserNotificationPreference(Base):
    """
    Model for storing user-specific notification preferences and settings.
    
    This model manages individual user preferences for receiving notifications
    across different channels and types, enabling personalized notification
    experiences and compliance with user communication preferences.
    
    Attributes:
        id (UUID): Unique identifier for the preference record
        user_id (str): ID of the user (from naebak-auth-service)
        notification_type (NotificationType): Type of notification
        channel (NotificationChannel): Delivery channel
        is_enabled (bool): Whether notifications of this type/channel are enabled
        frequency (str): Delivery frequency (immediate, daily, weekly)
        quiet_hours_start (str): Start time for quiet hours (HH:MM format)
        quiet_hours_end (str): End time for quiet hours (HH:MM format)
        timezone (str): User's timezone for scheduling
        created_at (datetime): Preference creation timestamp
        updated_at (datetime): Last modification timestamp
    
    Frequency Options:
        - immediate: Send notifications immediately
        - daily: Batch notifications daily
        - weekly: Batch notifications weekly
        - disabled: Do not send notifications
    
    Quiet Hours:
        Users can specify quiet hours during which non-urgent notifications
        should not be delivered. Urgent notifications may override this setting.
    
    Example:
        A user might prefer:
        - Email notifications for complaints: enabled, immediate
        - SMS notifications for security: enabled, immediate
        - Push notifications for messages: enabled, daily batching
        - Marketing emails: disabled
    """
    __tablename__ = 'user_notification_preferences'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50), nullable=False)  # From naebak-auth-service
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    is_enabled = Column(Boolean, default=True)
    frequency = Column(String(20), default='immediate')  # immediate, daily, weekly
    quiet_hours_start = Column(String(5))  # HH:MM format
    quiet_hours_end = Column(String(5))    # HH:MM format
    timezone = Column(String(50), default='UTC')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite unique constraint to prevent duplicate preferences
    __table_args__ = (
        {'extend_existing': True}
    )
    
    def __repr__(self):
        return f"<UserNotificationPreference(user_id='{self.user_id}', type='{self.notification_type.value}', channel='{self.channel.value}', enabled={self.is_enabled})>"

class Notification(Base):
    """
    Model for storing individual notification records and delivery tracking.
    
    This model represents individual notification instances, tracking their
    content, delivery status, and metadata throughout the notification lifecycle
    from creation to final delivery confirmation.
    
    Attributes:
        id (UUID): Unique identifier for the notification
        user_id (str): ID of the recipient user
        template_id (UUID): ID of the template used (optional)
        notification_type (NotificationType): Type of notification
        channel (NotificationChannel): Delivery channel
        priority (NotificationPriority): Processing priority
        subject (str): Notification subject (for email)
        content (str): Final rendered notification content
        variables (JSON): Variables used for template rendering
        status (NotificationStatus): Current delivery status
        scheduled_at (datetime): When the notification should be sent
        sent_at (datetime): When the notification was actually sent
        delivered_at (datetime): When delivery was confirmed
        failed_at (datetime): When delivery failed (if applicable)
        retry_count (int): Number of delivery attempts
        max_retries (int): Maximum number of retry attempts
        error_message (str): Error details if delivery failed
        provider_response (JSON): Response from delivery provider
        created_at (datetime): Notification creation timestamp
        updated_at (datetime): Last status update timestamp
    
    Delivery Tracking:
        The model tracks the complete delivery lifecycle with timestamps
        for each stage, enabling comprehensive monitoring and analytics.
    
    Retry Logic:
        Failed notifications can be retried up to max_retries times,
        with exponential backoff and detailed error tracking.
    
    Provider Integration:
        The provider_response field stores responses from external
        delivery providers (SendGrid, Twilio, FCM) for debugging
        and delivery confirmation.
    """
    __tablename__ = 'notifications'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey('notification_templates.id'))
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    priority = Column(Enum(NotificationPriority), default=NotificationPriority.NORMAL)
    
    # Content
    subject = Column(String(500))  # For email notifications
    content = Column(Text, nullable=False)
    variables = Column(JSON)  # Variables used for rendering
    
    # Status tracking
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    scheduled_at = Column(DateTime)  # For scheduled notifications
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    failed_at = Column(DateTime)
    
    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text)
    provider_response = Column(JSON)  # Response from delivery provider
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    template = relationship("NotificationTemplate", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id='{self.id}', user_id='{self.user_id}', type='{self.notification_type.value}', status='{self.status.value}')>"
    
    def can_retry(self):
        """
        Check if the notification can be retried based on retry count and status.
        
        Returns:
            bool: True if the notification can be retried, False otherwise.
        """
        return (self.status == NotificationStatus.FAILED and 
                self.retry_count < self.max_retries)
    
    def mark_sent(self, provider_response=None):
        """
        Mark the notification as sent with optional provider response.
        
        Args:
            provider_response (dict, optional): Response from delivery provider.
        """
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.utcnow()
        if provider_response:
            self.provider_response = provider_response
    
    def mark_delivered(self, provider_response=None):
        """
        Mark the notification as delivered with optional provider response.
        
        Args:
            provider_response (dict, optional): Response from delivery provider.
        """
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
        if provider_response:
            self.provider_response = provider_response
    
    def mark_failed(self, error_message, provider_response=None):
        """
        Mark the notification as failed with error details.
        
        Args:
            error_message (str): Error message describing the failure.
            provider_response (dict, optional): Response from delivery provider.
        """
        self.status = NotificationStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.error_message = error_message
        self.retry_count += 1
        if provider_response:
            self.provider_response = provider_response

class NotificationBatch(Base):
    """
    Model for managing batched notification delivery.
    
    This model supports batching multiple notifications for efficient
    delivery, particularly useful for digest emails and bulk communications.
    
    Attributes:
        id (UUID): Unique identifier for the batch
        user_id (str): ID of the recipient user
        notification_type (NotificationType): Type of notifications in batch
        channel (NotificationChannel): Delivery channel for the batch
        batch_size (int): Number of notifications in the batch
        status (NotificationStatus): Batch delivery status
        scheduled_at (datetime): When the batch should be sent
        sent_at (datetime): When the batch was sent
        created_at (datetime): Batch creation timestamp
        updated_at (datetime): Last status update timestamp
    
    Batching Strategy:
        Notifications can be batched based on user preferences, reducing
        notification fatigue and improving delivery efficiency for
        non-urgent communications.
    """
    __tablename__ = 'notification_batches'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50), nullable=False)
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    batch_size = Column(Integer, default=0)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<NotificationBatch(id='{self.id}', user_id='{self.user_id}', size={self.batch_size}, status='{self.status.value}')>"

# Database configuration and session management
def create_database_engine(database_url):
    """
    Create SQLAlchemy engine with optimized settings for the notifications service.
    
    Args:
        database_url (str): PostgreSQL database connection URL.
        
    Returns:
        Engine: Configured SQLAlchemy engine.
    """
    engine = create_engine(
        database_url,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False  # Set to True for SQL debugging
    )
    return engine

def create_database_session(engine):
    """
    Create SQLAlchemy session factory for database operations.
    
    Args:
        engine (Engine): SQLAlchemy engine.
        
    Returns:
        sessionmaker: Session factory for creating database sessions.
    """
    Session = sessionmaker(bind=engine)
    return Session

def init_database(database_url):
    """
    Initialize database with all tables and return session factory.
    
    Args:
        database_url (str): PostgreSQL database connection URL.
        
    Returns:
        tuple: (engine, session_factory) for database operations.
    """
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = create_database_session(engine)
    return engine, session_factory

# Utility functions for model operations
def get_user_preferences(session, user_id):
    """
    Retrieve all notification preferences for a specific user.
    
    Args:
        session: SQLAlchemy database session.
        user_id (str): ID of the user.
        
    Returns:
        list: List of UserNotificationPreference objects.
    """
    return session.query(UserNotificationPreference).filter_by(user_id=user_id).all()

def get_active_template(session, notification_type, channel):
    """
    Retrieve the active template for a specific notification type and channel.
    
    Args:
        session: SQLAlchemy database session.
        notification_type (NotificationType): Type of notification.
        channel (NotificationChannel): Delivery channel.
        
    Returns:
        NotificationTemplate: Active template or None if not found.
    """
    return session.query(NotificationTemplate).filter_by(
        notification_type=notification_type,
        channel=channel,
        is_active=True
    ).first()

def create_notification(session, user_id, notification_type, channel, content, **kwargs):
    """
    Create a new notification record in the database.
    
    Args:
        session: SQLAlchemy database session.
        user_id (str): ID of the recipient user.
        notification_type (NotificationType): Type of notification.
        channel (NotificationChannel): Delivery channel.
        content (str): Notification content.
        **kwargs: Additional notification attributes.
        
    Returns:
        Notification: Created notification object.
    """
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        channel=channel,
        content=content,
        **kwargs
    )
    session.add(notification)
    session.commit()
    return notification
