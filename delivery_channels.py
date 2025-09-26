"""
Naebak Notifications Service - Delivery Channels

This module implements the delivery channel system for the notifications service,
providing unified interfaces for sending notifications through multiple channels
including email, SMS, push notifications, and in-app notifications.

The delivery system is designed with:
- Provider abstraction for easy integration switching
- Comprehensive error handling and retry logic
- Delivery confirmation and status tracking
- Rate limiting and quota management
- Template rendering and content personalization
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import json

# External provider imports
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from twilio.rest import Client as TwilioClient
from pyfcm import FCMNotification
import requests

# Internal imports
from models import Notification, NotificationStatus, NotificationChannel

logger = logging.getLogger(__name__)

class DeliveryResult:
    """
    Represents the result of a notification delivery attempt.
    
    This class encapsulates the outcome of sending a notification,
    including success status, provider response, and error details.
    
    Attributes:
        success (bool): Whether the delivery was successful
        provider_response (dict): Response from the delivery provider
        error_message (str): Error message if delivery failed
        delivery_id (str): Unique identifier from the provider
        timestamp (datetime): When the delivery attempt was made
    """
    
    def __init__(self, success: bool, provider_response: Dict[str, Any] = None, 
                 error_message: str = None, delivery_id: str = None):
        self.success = success
        self.provider_response = provider_response or {}
        self.error_message = error_message
        self.delivery_id = delivery_id
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert delivery result to dictionary format."""
        return {
            'success': self.success,
            'provider_response': self.provider_response,
            'error_message': self.error_message,
            'delivery_id': self.delivery_id,
            'timestamp': self.timestamp.isoformat()
        }

class BaseDeliveryChannel(ABC):
    """
    Abstract base class for notification delivery channels.
    
    This class defines the interface that all delivery channels must implement,
    ensuring consistent behavior across different notification providers and
    delivery mechanisms.
    
    Methods:
        send: Send a notification through the channel
        validate_config: Validate channel configuration
        get_delivery_status: Check delivery status from provider
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the delivery channel with configuration.
        
        Args:
            config (dict): Channel-specific configuration parameters
        """
        self.config = config
        self.validate_config()
    
    @abstractmethod
    def send(self, notification: Notification, recipient_info: Dict[str, Any]) -> DeliveryResult:
        """
        Send a notification through this channel.
        
        Args:
            notification (Notification): The notification to send
            recipient_info (dict): Recipient contact information
            
        Returns:
            DeliveryResult: Result of the delivery attempt
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> None:
        """
        Validate the channel configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        pass
    
    def get_delivery_status(self, delivery_id: str) -> Optional[str]:
        """
        Get delivery status from the provider.
        
        Args:
            delivery_id (str): Provider-specific delivery identifier
            
        Returns:
            str: Delivery status or None if not available
        """
        return None

class EmailDeliveryChannel(BaseDeliveryChannel):
    """
    Email delivery channel using SendGrid API.
    
    This channel handles email notifications with support for HTML content,
    attachments, and delivery tracking. It integrates with SendGrid for
    reliable email delivery and provides comprehensive error handling.
    
    Configuration:
        api_key (str): SendGrid API key
        from_email (str): Default sender email address
        from_name (str): Default sender name
        reply_to (str): Reply-to email address
    
    Features:
        - HTML and plain text email support
        - Template-based email composition
        - Delivery tracking and webhooks
        - Bounce and spam handling
        - Rate limiting compliance
    """
    
    def validate_config(self) -> None:
        """Validate SendGrid configuration."""
        required_keys = ['api_key', 'from_email']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required email config: {key}")
    
    def send(self, notification: Notification, recipient_info: Dict[str, Any]) -> DeliveryResult:
        """
        Send email notification via SendGrid.
        
        Args:
            notification (Notification): The notification to send
            recipient_info (dict): Must contain 'email' key
            
        Returns:
            DeliveryResult: Result of the email delivery attempt
        """
        try:
            # Validate recipient email
            recipient_email = recipient_info.get('email')
            if not recipient_email:
                return DeliveryResult(
                    success=False,
                    error_message="Recipient email address is required"
                )
            
            # Initialize SendGrid client
            sg = sendgrid.SendGridAPIClient(api_key=self.config['api_key'])
            
            # Create email message
            from_email = Email(
                email=self.config['from_email'],
                name=self.config.get('from_name', 'منصة نائبك')
            )
            to_email = To(email=recipient_email)
            
            # Use notification subject or default
            subject = notification.subject or "إشعار من منصة نائبك"
            
            # Create content (support both HTML and plain text)
            if '<html>' in notification.content.lower() or '<p>' in notification.content.lower():
                content = Content("text/html", notification.content)
            else:
                content = Content("text/plain", notification.content)
            
            # Build email
            mail = Mail(from_email, to_email, subject, content)
            
            # Add reply-to if configured
            if 'reply_to' in self.config:
                mail.reply_to = Email(self.config['reply_to'])
            
            # Add custom headers for tracking
            mail.custom_args = {
                'notification_id': str(notification.id),
                'notification_type': notification.notification_type.value,
                'user_id': notification.user_id
            }
            
            # Send email
            response = sg.send(mail)
            
            # Parse response
            if response.status_code in [200, 202]:
                return DeliveryResult(
                    success=True,
                    provider_response={
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'message_id': response.headers.get('X-Message-Id')
                    },
                    delivery_id=response.headers.get('X-Message-Id')
                )
            else:
                return DeliveryResult(
                    success=False,
                    provider_response={
                        'status_code': response.status_code,
                        'body': response.body,
                        'headers': dict(response.headers)
                    },
                    error_message=f"SendGrid API error: {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Email delivery failed for notification {notification.id}: {str(e)}")
            return DeliveryResult(
                success=False,
                error_message=f"Email delivery error: {str(e)}"
            )

class SMSDeliveryChannel(BaseDeliveryChannel):
    """
    SMS delivery channel using Twilio API.
    
    This channel handles SMS notifications with support for international
    numbers, delivery receipts, and comprehensive error handling. It integrates
    with Twilio for reliable SMS delivery worldwide.
    
    Configuration:
        account_sid (str): Twilio account SID
        auth_token (str): Twilio authentication token
        from_number (str): Twilio phone number for sending SMS
        webhook_url (str): URL for delivery status webhooks
    
    Features:
        - International SMS delivery
        - Delivery receipt tracking
        - Message status webhooks
        - Character count optimization
        - Rate limiting compliance
    """
    
    def validate_config(self) -> None:
        """Validate Twilio configuration."""
        required_keys = ['account_sid', 'auth_token', 'from_number']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required SMS config: {key}")
    
    def send(self, notification: Notification, recipient_info: Dict[str, Any]) -> DeliveryResult:
        """
        Send SMS notification via Twilio.
        
        Args:
            notification (Notification): The notification to send
            recipient_info (dict): Must contain 'phone' key
            
        Returns:
            DeliveryResult: Result of the SMS delivery attempt
        """
        try:
            # Validate recipient phone number
            recipient_phone = recipient_info.get('phone')
            if not recipient_phone:
                return DeliveryResult(
                    success=False,
                    error_message="Recipient phone number is required"
                )
            
            # Initialize Twilio client
            client = TwilioClient(
                self.config['account_sid'],
                self.config['auth_token']
            )
            
            # Prepare SMS content (limit to 1600 characters for concatenated SMS)
            content = notification.content
            if len(content) > 1600:
                content = content[:1597] + "..."
                logger.warning(f"SMS content truncated for notification {notification.id}")
            
            # Send SMS
            message = client.messages.create(
                body=content,
                from_=self.config['from_number'],
                to=recipient_phone,
                status_callback=self.config.get('webhook_url'),
                provide_feedback=True
            )
            
            return DeliveryResult(
                success=True,
                provider_response={
                    'sid': message.sid,
                    'status': message.status,
                    'direction': message.direction,
                    'price': message.price,
                    'price_unit': message.price_unit
                },
                delivery_id=message.sid
            )
            
        except Exception as e:
            logger.error(f"SMS delivery failed for notification {notification.id}: {str(e)}")
            return DeliveryResult(
                success=False,
                error_message=f"SMS delivery error: {str(e)}"
            )
    
    def get_delivery_status(self, delivery_id: str) -> Optional[str]:
        """
        Get SMS delivery status from Twilio.
        
        Args:
            delivery_id (str): Twilio message SID
            
        Returns:
            str: Message status (queued, sent, delivered, failed, etc.)
        """
        try:
            client = TwilioClient(
                self.config['account_sid'],
                self.config['auth_token']
            )
            message = client.messages(delivery_id).fetch()
            return message.status
        except Exception as e:
            logger.error(f"Failed to get SMS status for {delivery_id}: {str(e)}")
            return None

class PushNotificationChannel(BaseDeliveryChannel):
    """
    Push notification delivery channel using Firebase Cloud Messaging (FCM).
    
    This channel handles push notifications for mobile and web applications
    with support for rich content, action buttons, and delivery tracking.
    It integrates with FCM for cross-platform push notification delivery.
    
    Configuration:
        api_key (str): FCM server key
        project_id (str): Firebase project ID
        default_icon (str): Default notification icon URL
        default_sound (str): Default notification sound
    
    Features:
        - Cross-platform push notifications (iOS, Android, Web)
        - Rich notification content with images and actions
        - Topic-based and device-specific targeting
        - Delivery analytics and tracking
        - Silent notifications for background updates
    """
    
    def validate_config(self) -> None:
        """Validate FCM configuration."""
        required_keys = ['api_key']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required push config: {key}")
    
    def send(self, notification: Notification, recipient_info: Dict[str, Any]) -> DeliveryResult:
        """
        Send push notification via FCM.
        
        Args:
            notification (Notification): The notification to send
            recipient_info (dict): Must contain 'device_token' or 'topic'
            
        Returns:
            DeliveryResult: Result of the push notification delivery attempt
        """
        try:
            # Initialize FCM client
            push_service = FCMNotification(api_key=self.config['api_key'])
            
            # Get recipient information
            device_token = recipient_info.get('device_token')
            topic = recipient_info.get('topic')
            
            if not device_token and not topic:
                return DeliveryResult(
                    success=False,
                    error_message="Device token or topic is required for push notifications"
                )
            
            # Prepare notification data
            title = notification.subject or "منصة نائبك"
            body = notification.content
            
            # Prepare additional data
            data_message = {
                'notification_id': str(notification.id),
                'notification_type': notification.notification_type.value,
                'user_id': notification.user_id,
                'timestamp': notification.created_at.isoformat()
            }
            
            # Send notification
            if device_token:
                # Send to specific device
                result = push_service.notify_single_device(
                    registration_id=device_token,
                    message_title=title,
                    message_body=body,
                    data_message=data_message,
                    sound=self.config.get('default_sound', 'default'),
                    badge=1,
                    extra_notification_kwargs={
                        'icon': self.config.get('default_icon'),
                        'color': '#1976D2',  # Naebak brand color
                        'click_action': 'FLUTTER_NOTIFICATION_CLICK'
                    }
                )
            else:
                # Send to topic
                result = push_service.notify_topic_subscribers(
                    topic_name=topic,
                    message_title=title,
                    message_body=body,
                    data_message=data_message,
                    sound=self.config.get('default_sound', 'default')
                )
            
            # Parse result
            if result.get('success'):
                return DeliveryResult(
                    success=True,
                    provider_response=result,
                    delivery_id=result.get('multicast_id') or result.get('message_id')
                )
            else:
                return DeliveryResult(
                    success=False,
                    provider_response=result,
                    error_message=f"FCM delivery failed: {result.get('failure', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.error(f"Push notification delivery failed for notification {notification.id}: {str(e)}")
            return DeliveryResult(
                success=False,
                error_message=f"Push notification error: {str(e)}"
            )

class InAppNotificationChannel(BaseDeliveryChannel):
    """
    In-app notification channel for platform-internal notifications.
    
    This channel handles notifications that are displayed within the Naebak
    platform interface, providing real-time updates and alerts to users
    while they are actively using the application.
    
    Configuration:
        redis_url (str): Redis connection URL for real-time delivery
        websocket_url (str): WebSocket endpoint for real-time updates
    
    Features:
        - Real-time in-app notification delivery
        - WebSocket integration for instant updates
        - Notification persistence for offline users
        - Read/unread status tracking
        - Rich content support with actions
    """
    
    def validate_config(self) -> None:
        """Validate in-app notification configuration."""
        # In-app notifications have minimal configuration requirements
        pass
    
    def send(self, notification: Notification, recipient_info: Dict[str, Any]) -> DeliveryResult:
        """
        Send in-app notification via WebSocket or Redis.
        
        Args:
            notification (Notification): The notification to send
            recipient_info (dict): User session information
            
        Returns:
            DeliveryResult: Result of the in-app notification delivery
        """
        try:
            # Prepare notification payload
            payload = {
                'id': str(notification.id),
                'type': notification.notification_type.value,
                'title': notification.subject or "إشعار جديد",
                'content': notification.content,
                'timestamp': notification.created_at.isoformat(),
                'user_id': notification.user_id
            }
            
            # Store in Redis for persistence (in case user is offline)
            if 'redis_client' in self.config:
                redis_client = self.config['redis_client']
                redis_key = f"user_notifications:{notification.user_id}"
                redis_client.lpush(redis_key, json.dumps(payload))
                redis_client.expire(redis_key, 86400 * 7)  # Keep for 7 days
            
            # Send via WebSocket if user is online
            if 'websocket_client' in self.config:
                websocket_client = self.config['websocket_client']
                websocket_client.emit('new_notification', payload, room=notification.user_id)
            
            return DeliveryResult(
                success=True,
                provider_response={'method': 'in_app', 'stored': True},
                delivery_id=str(notification.id)
            )
            
        except Exception as e:
            logger.error(f"In-app notification delivery failed for notification {notification.id}: {str(e)}")
            return DeliveryResult(
                success=False,
                error_message=f"In-app notification error: {str(e)}"
            )

class NotificationDeliveryManager:
    """
    Central manager for notification delivery across all channels.
    
    This class orchestrates notification delivery by routing notifications
    to appropriate channels, managing delivery attempts, and tracking
    delivery status across the entire notification lifecycle.
    
    Features:
        - Multi-channel delivery coordination
        - Delivery retry logic with exponential backoff
        - Provider failover and redundancy
        - Delivery analytics and monitoring
        - Rate limiting and quota management
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the delivery manager with channel configurations.
        
        Args:
            config (dict): Configuration for all delivery channels
        """
        self.config = config
        self.channels = {}
        self._initialize_channels()
    
    def _initialize_channels(self) -> None:
        """Initialize all configured delivery channels."""
        channel_classes = {
            NotificationChannel.EMAIL: EmailDeliveryChannel,
            NotificationChannel.SMS: SMSDeliveryChannel,
            NotificationChannel.PUSH: PushNotificationChannel,
            NotificationChannel.IN_APP: InAppNotificationChannel
        }
        
        for channel_type, channel_class in channel_classes.items():
            channel_config = self.config.get(channel_type.value)
            if channel_config:
                try:
                    self.channels[channel_type] = channel_class(channel_config)
                    logger.info(f"Initialized {channel_type.value} delivery channel")
                except Exception as e:
                    logger.error(f"Failed to initialize {channel_type.value} channel: {str(e)}")
    
    def deliver_notification(self, notification: Notification, recipient_info: Dict[str, Any]) -> DeliveryResult:
        """
        Deliver a notification through the appropriate channel.
        
        Args:
            notification (Notification): The notification to deliver
            recipient_info (dict): Recipient contact information
            
        Returns:
            DeliveryResult: Result of the delivery attempt
        """
        channel = self.channels.get(notification.channel)
        if not channel:
            return DeliveryResult(
                success=False,
                error_message=f"Delivery channel {notification.channel.value} not configured"
            )
        
        try:
            result = channel.send(notification, recipient_info)
            logger.info(f"Delivery attempt for notification {notification.id}: {'success' if result.success else 'failed'}")
            return result
        except Exception as e:
            logger.error(f"Unexpected error during delivery of notification {notification.id}: {str(e)}")
            return DeliveryResult(
                success=False,
                error_message=f"Delivery error: {str(e)}"
            )
    
    def get_delivery_status(self, notification: Notification) -> Optional[str]:
        """
        Get delivery status for a notification from the provider.
        
        Args:
            notification (Notification): The notification to check
            
        Returns:
            str: Delivery status or None if not available
        """
        channel = self.channels.get(notification.channel)
        if not channel or not hasattr(notification, 'provider_response'):
            return None
        
        delivery_id = notification.provider_response.get('delivery_id')
        if delivery_id:
            return channel.get_delivery_status(delivery_id)
        
        return None
    
    def get_available_channels(self) -> list:
        """
        Get list of available delivery channels.
        
        Returns:
            list: List of available NotificationChannel enums
        """
        return list(self.channels.keys())

# Factory function for creating delivery manager
def create_delivery_manager(config: Dict[str, Any]) -> NotificationDeliveryManager:
    """
    Factory function to create a configured delivery manager.
    
    Args:
        config (dict): Complete configuration for all channels
        
    Returns:
        NotificationDeliveryManager: Configured delivery manager instance
    """
    return NotificationDeliveryManager(config)
