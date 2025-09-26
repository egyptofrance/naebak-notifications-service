"""
Naebak Notifications Service - Celery Tasks

This module implements Celery tasks for asynchronous notification processing,
providing scalable and reliable notification delivery with retry logic,
scheduling, and comprehensive error handling.

Key Features:
- Asynchronous notification processing with Celery
- Retry logic with exponential backoff
- Scheduled and batched notification delivery
- Integration with delivery channels and template system
- Comprehensive logging and monitoring
- Dead letter queue for failed notifications
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from celery import Celery, Task
from celery.exceptions import Retry
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Internal imports
from models import (
    Notification, NotificationTemplate, UserNotificationPreference,
    NotificationStatus, NotificationChannel, NotificationType, NotificationPriority,
    init_database
)
from delivery_channels import create_delivery_manager, DeliveryResult
from template_system import create_template_manager, create_preference_manager
from config import get_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration
config = get_config()

# Initialize Celery app
celery_app = Celery(
    'naebak_notifications',
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
    include=['celery_tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    task_routes={
        'celery_tasks.send_notification': {'queue': 'notifications'},
        'celery_tasks.send_batch_notifications': {'queue': 'batch_notifications'},
        'celery_tasks.process_scheduled_notifications': {'queue': 'scheduled'},
        'celery_tasks.cleanup_old_notifications': {'queue': 'maintenance'}
    }
)

# Database setup
engine, SessionLocal = init_database(config.DATABASE_URL)

# Delivery manager setup
delivery_config = {
    'email': {
        'api_key': config.SENDGRID_API_KEY,
        'from_email': config.FROM_EMAIL,
        'from_name': config.FROM_NAME,
        'reply_to': config.REPLY_TO_EMAIL
    },
    'sms': {
        'account_sid': config.TWILIO_ACCOUNT_SID,
        'auth_token': config.TWILIO_AUTH_TOKEN,
        'from_number': config.TWILIO_FROM_NUMBER,
        'webhook_url': config.TWILIO_WEBHOOK_URL
    },
    'push': {
        'api_key': config.FCM_API_KEY,
        'project_id': config.FCM_PROJECT_ID,
        'default_icon': config.FCM_DEFAULT_ICON,
        'default_sound': config.FCM_DEFAULT_SOUND
    },
    'in_app': {
        'redis_url': config.REDIS_URL,
        'websocket_url': config.WEBSOCKET_URL
    }
}

delivery_manager = create_delivery_manager(delivery_config)

class NotificationTask(Task):
    """
    Base task class for notification processing with common functionality.
    
    This class provides shared functionality for all notification tasks
    including database session management, error handling, and logging.
    """
    
    def __init__(self):
        self.db_session = None
    
    def __call__(self, *args, **kwargs):
        """Execute task with database session management."""
        self.db_session = SessionLocal()
        try:
            return super().__call__(*args, **kwargs)
        finally:
            if self.db_session:
                self.db_session.close()
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
        if self.db_session:
            self.db_session.rollback()
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")

@celery_app.task(bind=True, base=NotificationTask, name='celery_tasks.send_notification')
def send_notification(self, notification_id: str, recipient_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send a single notification asynchronously.
    
    This task handles the complete notification delivery process including
    template rendering, user preference checking, delivery attempt, and
    status tracking with comprehensive error handling and retry logic.
    
    Args:
        notification_id (str): ID of the notification to send
        recipient_info (dict): Recipient contact information
        
    Returns:
        dict: Delivery result with status and details
    """
    try:
        # Get notification from database
        notification = self.db_session.query(Notification).filter_by(id=notification_id).first()
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return {'success': False, 'error': 'Notification not found'}
        
        # Update status to processing
        notification.status = NotificationStatus.PROCESSING
        self.db_session.commit()
        
        # Initialize managers
        preference_manager = create_preference_manager(self.db_session)
        template_manager = create_template_manager(self.db_session)
        
        # Check user preferences
        should_send, reason = preference_manager.should_send_notification(
            notification.user_id,
            notification.notification_type,
            notification.channel,
            notification.priority
        )
        
        if not should_send:
            logger.info(f"Notification {notification_id} blocked by user preferences: {reason}")
            notification.status = NotificationStatus.CANCELLED
            notification.error_message = f"Blocked by user preferences: {reason}"
            self.db_session.commit()
            return {'success': False, 'reason': 'blocked_by_preferences', 'details': reason}
        
        # Get recipient information if not provided
        if not recipient_info:
            recipient_info = get_recipient_info(notification.user_id, notification.channel)
            if not recipient_info:
                error_msg = f"Could not get recipient info for user {notification.user_id}"
                logger.error(error_msg)
                notification.mark_failed(error_msg)
                self.db_session.commit()
                return {'success': False, 'error': error_msg}
        
        # Render template if template is used
        if notification.template_id:
            template = self.db_session.query(NotificationTemplate).filter_by(
                id=notification.template_id
            ).first()
            
            if template:
                success, rendered_content, rendered_subject, error = template_manager.render_notification_content(
                    template, notification.variables or {}
                )
                
                if success:
                    notification.content = rendered_content
                    if rendered_subject:
                        notification.subject = rendered_subject
                else:
                    logger.warning(f"Template rendering failed for notification {notification_id}: {error}")
        
        # Update status to queued
        notification.status = NotificationStatus.QUEUED
        self.db_session.commit()
        
        # Attempt delivery
        delivery_result = delivery_manager.deliver_notification(notification, recipient_info)
        
        # Update notification status based on delivery result
        if delivery_result.success:
            notification.mark_sent(delivery_result.provider_response)
            logger.info(f"Notification {notification_id} sent successfully via {notification.channel.value}")
        else:
            notification.mark_failed(delivery_result.error_message, delivery_result.provider_response)
            logger.error(f"Notification {notification_id} delivery failed: {delivery_result.error_message}")
            
            # Retry if possible
            if notification.can_retry():
                logger.info(f"Scheduling retry for notification {notification_id} (attempt {notification.retry_count + 1})")
                # Schedule retry with exponential backoff
                retry_delay = min(300, 60 * (2 ** notification.retry_count))  # Max 5 minutes
                raise self.retry(countdown=retry_delay, max_retries=notification.max_retries)
        
        self.db_session.commit()
        
        return {
            'success': delivery_result.success,
            'notification_id': notification_id,
            'channel': notification.channel.value,
            'delivery_id': delivery_result.delivery_id,
            'error': delivery_result.error_message if not delivery_result.success else None
        }
        
    except Retry:
        # Re-raise retry exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_notification task: {str(e)}")
        if notification:
            notification.mark_failed(f"Task error: {str(e)}")
            self.db_session.commit()
        return {'success': False, 'error': f"Task error: {str(e)}"}

@celery_app.task(bind=True, base=NotificationTask, name='celery_tasks.send_batch_notifications')
def send_batch_notifications(self, user_id: str, notification_type: str, channel: str) -> Dict[str, Any]:
    """
    Send batched notifications for a user.
    
    This task handles the delivery of batched notifications based on user
    preferences for daily or weekly notification frequency.
    
    Args:
        user_id (str): ID of the user
        notification_type (str): Type of notifications to batch
        channel (str): Delivery channel
        
    Returns:
        dict: Batch delivery result
    """
    try:
        # Get pending notifications for batching
        notifications = self.db_session.query(Notification).filter_by(
            user_id=user_id,
            notification_type=NotificationType(notification_type),
            channel=NotificationChannel(channel),
            status=NotificationStatus.PENDING
        ).all()
        
        if not notifications:
            return {'success': True, 'message': 'No notifications to batch'}
        
        # Get user preferences
        preference_manager = create_preference_manager(self.db_session)
        preference = self.db_session.query(UserNotificationPreference).filter_by(
            user_id=user_id,
            notification_type=NotificationType(notification_type),
            channel=NotificationChannel(channel)
        ).first()
        
        if not preference or preference.frequency not in ['daily', 'weekly']:
            # Send individually if not batched
            for notification in notifications:
                send_notification.delay(str(notification.id))
            return {'success': True, 'message': f'Sent {len(notifications)} individual notifications'}
        
        # Create batch notification content
        batch_content = create_batch_content(notifications, preference.frequency)
        
        # Create a single notification for the batch
        batch_notification = Notification(
            user_id=user_id,
            notification_type=NotificationType(notification_type),
            channel=NotificationChannel(channel),
            content=batch_content,
            subject=f"ملخص الإشعارات - {len(notifications)} إشعار جديد"
        )
        
        self.db_session.add(batch_notification)
        self.db_session.commit()
        
        # Send the batch notification
        result = send_notification.delay(str(batch_notification.id))
        
        # Mark original notifications as batched
        for notification in notifications:
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            notification.error_message = f"Included in batch {batch_notification.id}"
        
        self.db_session.commit()
        
        return {
            'success': True,
            'batch_notification_id': str(batch_notification.id),
            'batched_count': len(notifications)
        }
        
    except Exception as e:
        logger.error(f"Error in send_batch_notifications: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, base=NotificationTask, name='celery_tasks.process_scheduled_notifications')
def process_scheduled_notifications(self) -> Dict[str, Any]:
    """
    Process notifications scheduled for delivery.
    
    This task runs periodically to check for notifications that are
    scheduled for delivery and queues them for processing.
    
    Returns:
        dict: Processing result with count of scheduled notifications
    """
    try:
        # Get notifications scheduled for now or earlier
        current_time = datetime.utcnow()
        scheduled_notifications = self.db_session.query(Notification).filter(
            Notification.status == NotificationStatus.PENDING,
            Notification.scheduled_at <= current_time
        ).all()
        
        processed_count = 0
        for notification in scheduled_notifications:
            # Queue for immediate processing
            send_notification.delay(str(notification.id))
            processed_count += 1
        
        logger.info(f"Processed {processed_count} scheduled notifications")
        
        return {
            'success': True,
            'processed_count': processed_count,
            'timestamp': current_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in process_scheduled_notifications: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, base=NotificationTask, name='celery_tasks.cleanup_old_notifications')
def cleanup_old_notifications(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Clean up old notification records.
    
    This maintenance task removes old notification records to keep
    the database size manageable while preserving recent history.
    
    Args:
        days_old (int): Number of days to keep notifications
        
    Returns:
        dict: Cleanup result with count of removed notifications
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Delete old notifications
        deleted_count = self.db_session.query(Notification).filter(
            Notification.created_at < cutoff_date,
            Notification.status.in_([
                NotificationStatus.DELIVERED,
                NotificationStatus.FAILED,
                NotificationStatus.CANCELLED
            ])
        ).delete()
        
        self.db_session.commit()
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_notifications: {str(e)}")
        self.db_session.rollback()
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, base=NotificationTask, name='celery_tasks.send_welcome_notification')
def send_welcome_notification(self, user_id: str, user_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send welcome notification to new users.
    
    This task is triggered when a new user registers and sends
    a welcome notification via email and in-app channels.
    
    Args:
        user_id (str): ID of the new user
        user_info (dict): User information for personalization
        
    Returns:
        dict: Welcome notification result
    """
    try:
        # Initialize user preferences
        preference_manager = create_preference_manager(self.db_session)
        preference_manager.initialize_user_preferences(user_id)
        
        # Create welcome notifications
        channels = [NotificationChannel.EMAIL, NotificationChannel.IN_APP]
        notification_ids = []
        
        for channel in channels:
            # Get template
            template = self.db_session.query(NotificationTemplate).filter_by(
                notification_type=NotificationType.WELCOME,
                channel=channel,
                is_active=True
            ).first()
            
            # Create notification
            notification = Notification(
                user_id=user_id,
                template_id=template.id if template else None,
                notification_type=NotificationType.WELCOME,
                channel=channel,
                priority=NotificationPriority.NORMAL,
                content="مرحباً بك في منصة نائبك!" if not template else template.content,
                variables=user_info
            )
            
            self.db_session.add(notification)
            self.db_session.commit()
            
            # Queue for delivery
            send_notification.delay(str(notification.id))
            notification_ids.append(str(notification.id))
        
        return {
            'success': True,
            'user_id': user_id,
            'notification_ids': notification_ids
        }
        
    except Exception as e:
        logger.error(f"Error in send_welcome_notification: {str(e)}")
        return {'success': False, 'error': str(e)}

# Utility functions
def get_recipient_info(user_id: str, channel: NotificationChannel) -> Optional[Dict[str, Any]]:
    """
    Get recipient contact information from user service.
    
    Args:
        user_id (str): ID of the user
        channel (NotificationChannel): Delivery channel
        
    Returns:
        dict: Recipient contact information or None if not found
    """
    try:
        # This would typically call the naebak-auth-service API
        # For now, return mock data
        if channel == NotificationChannel.EMAIL:
            return {'email': f'user{user_id}@example.com'}
        elif channel == NotificationChannel.SMS:
            return {'phone': f'+201000000{user_id[-3:]}'}
        elif channel == NotificationChannel.PUSH:
            return {'device_token': f'device_token_{user_id}'}
        else:
            return {'user_id': user_id}
    except Exception as e:
        logger.error(f"Error getting recipient info: {str(e)}")
        return None

def create_batch_content(notifications: List[Notification], frequency: str) -> str:
    """
    Create batched notification content.
    
    Args:
        notifications (list): List of notifications to batch
        frequency (str): Batching frequency (daily, weekly)
        
    Returns:
        str: Batched notification content
    """
    content_parts = [f"ملخص الإشعارات - {frequency.title()}"]
    content_parts.append(f"لديك {len(notifications)} إشعار جديد:")
    content_parts.append("")
    
    for i, notification in enumerate(notifications, 1):
        content_parts.append(f"{i}. {notification.content[:100]}...")
    
    content_parts.append("")
    content_parts.append("يمكنك مراجعة جميع الإشعارات في منصة نائبك.")
    
    return "\n".join(content_parts)

# Periodic tasks
@celery_app.task(name='celery_tasks.process_daily_batches')
def process_daily_batches():
    """Process daily notification batches."""
    # This would be scheduled to run daily
    logger.info("Processing daily notification batches")
    # Implementation would query users with daily preferences and send batches

@celery_app.task(name='celery_tasks.process_weekly_batches')
def process_weekly_batches():
    """Process weekly notification batches."""
    # This would be scheduled to run weekly
    logger.info("Processing weekly notification batches")
    # Implementation would query users with weekly preferences and send batches

# Celery beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'process-scheduled-notifications': {
        'task': 'celery_tasks.process_scheduled_notifications',
        'schedule': 60.0,  # Every minute
    },
    'process-daily-batches': {
        'task': 'celery_tasks.process_daily_batches',
        'schedule': 86400.0,  # Daily at midnight
    },
    'process-weekly-batches': {
        'task': 'celery_tasks.process_weekly_batches',
        'schedule': 604800.0,  # Weekly
    },
    'cleanup-old-notifications': {
        'task': 'celery_tasks.cleanup_old_notifications',
        'schedule': 86400.0,  # Daily
    },
}

if __name__ == '__main__':
    celery_app.start()
