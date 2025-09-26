#!/usr/bin/env python3
"""
Naebak Notifications Service - Main Application
===============================================

Multi-channel notification service for the Naebak platform.
Handles email, SMS, push notifications, and in-app notifications.

Features:
- Multi-channel delivery (Email, SMS, Push, In-App)
- Template system with Arabic support
- Asynchronous processing with Celery
- Delivery status tracking
- Priority-based queuing
- User preferences management
- Notification history
- Analytics and reporting
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from celery import Celery
import redis
import json
import uuid
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import requests
from twilio.rest import Client as TwilioClient
from firebase_admin import credentials, messaging, initialize_app
import logging
from config import Config
from models.notification import Notification, NotificationTemplate, UserPreference
from models.user import User
from utils.template_engine import render_template
from utils.delivery_tracker import DeliveryTracker
from utils.analytics import NotificationAnalytics
import threading
import time
from datetime import timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
CORS(app)
jwt = JWTManager(app)
redis_client = redis.Redis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'], db=0)

# Initialize Celery for async processing
celery = Celery(
    app.import_name,
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['CELERY_RESULT_BACKEND']
)
celery.conf.update(app.config)

# Initialize external services
twilio_client = None
firebase_app = None

def init_external_services():
    """Initialize external notification services"""
    global twilio_client, firebase_app
    
    try:
        # Initialize Twilio for SMS
        if app.config.get('TWILIO_ACCOUNT_SID') and app.config.get('TWILIO_AUTH_TOKEN'):
            twilio_client = TwilioClient(
                app.config['TWILIO_ACCOUNT_SID'],
                app.config['TWILIO_AUTH_TOKEN']
            )
            logger.info("Twilio SMS service initialized")
        
        # Initialize Firebase for push notifications
        if app.config.get('FIREBASE_CREDENTIALS_PATH'):
            cred = credentials.Certificate(app.config['FIREBASE_CREDENTIALS_PATH'])
            firebase_app = initialize_app(cred)
            logger.info("Firebase push notification service initialized")
            
    except Exception as e:
        logger.error(f"Failed to initialize external services: {str(e)}")

class NotificationChannel:
    """Base class for notification channels"""
    
    def __init__(self, name):
        self.name = name
        self.delivery_tracker = DeliveryTracker()
    
    def send(self, notification_data):
        """Send notification through this channel"""
        raise NotImplementedError
    
    def validate_recipient(self, recipient):
        """Validate recipient for this channel"""
        raise NotImplementedError

class EmailChannel(NotificationChannel):
    """Email notification channel"""
    
    def __init__(self):
        super().__init__('email')
        self.smtp_server = app.config.get('SMTP_SERVER', 'localhost')
        self.smtp_port = app.config.get('SMTP_PORT', 587)
        self.smtp_username = app.config.get('SMTP_USERNAME')
        self.smtp_password = app.config.get('SMTP_PASSWORD')
        self.from_email = app.config.get('FROM_EMAIL', 'noreply@naebak.com')
    
    def send(self, notification_data):
        """Send email notification"""
        try:
            recipient = notification_data['recipient']
            subject = notification_data['subject']
            body = notification_data['body']
            html_body = notification_data.get('html_body')
            attachments = notification_data.get('attachments', [])
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Add text body
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Add HTML body if provided
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Add attachments
            for attachment in attachments:
                self._add_attachment(msg, attachment)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_username and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient}")
            return True, "Email sent successfully"
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")
            return False, str(e)
    
    def _add_attachment(self, msg, attachment):
        """Add attachment to email message"""
        try:
            with open(attachment['path'], 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment["filename"]}'
            )
            msg.attach(part)
            
        except Exception as e:
            logger.error(f"Failed to add attachment {attachment['filename']}: {str(e)}")
    
    def validate_recipient(self, recipient):
        """Validate email address"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, recipient) is not None

class SMSChannel(NotificationChannel):
    """SMS notification channel"""
    
    def __init__(self):
        super().__init__('sms')
        self.from_number = app.config.get('TWILIO_FROM_NUMBER')
    
    def send(self, notification_data):
        """Send SMS notification"""
        if not twilio_client:
            return False, "Twilio not configured"
        
        try:
            recipient = notification_data['recipient']
            body = notification_data['body']
            
            # Send SMS
            message = twilio_client.messages.create(
                body=body,
                from_=self.from_number,
                to=recipient
            )
            
            logger.info(f"SMS sent successfully to {recipient}, SID: {message.sid}")
            return True, f"SMS sent successfully, SID: {message.sid}"
            
        except Exception as e:
            logger.error(f"Failed to send SMS to {recipient}: {str(e)}")
            return False, str(e)
    
    def validate_recipient(self, recipient):
        """Validate phone number"""
        import re
        # Basic phone number validation (international format)
        phone_pattern = r'^\+[1-9]\d{1,14}$'
        return re.match(phone_pattern, recipient) is not None

class PushChannel(NotificationChannel):
    """Push notification channel"""
    
    def __init__(self):
        super().__init__('push')
    
    def send(self, notification_data):
        """Send push notification"""
        if not firebase_app:
            return False, "Firebase not configured"
        
        try:
            recipient_token = notification_data['recipient']
            title = notification_data['title']
            body = notification_data['body']
            data = notification_data.get('data', {})
            
            # Create message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data,
                token=recipient_token
            )
            
            # Send message
            response = messaging.send(message)
            
            logger.info(f"Push notification sent successfully, response: {response}")
            return True, f"Push notification sent successfully, response: {response}"
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            return False, str(e)
    
    def validate_recipient(self, recipient):
        """Validate FCM token"""
        # Basic validation - FCM tokens are typically long strings
        return isinstance(recipient, str) and len(recipient) > 50

class InAppChannel(NotificationChannel):
    """In-app notification channel"""
    
    def __init__(self):
        super().__init__('in_app')
    
    def send(self, notification_data):
        """Send in-app notification"""
        try:
            user_id = notification_data['recipient']
            title = notification_data['title']
            body = notification_data['body']
            data = notification_data.get('data', {})
            
            # Store notification in database
            notification = Notification.create({
                'user_id': user_id,
                'title': title,
                'body': body,
                'data': json.dumps(data),
                'channel': 'in_app',
                'status': 'delivered',
                'created_at': datetime.datetime.utcnow()
            })
            
            # Store in Redis for real-time delivery
            redis_key = f"user_notifications:{user_id}"
            notification_data_redis = {
                'id': notification.id,
                'title': title,
                'body': body,
                'data': data,
                'timestamp': datetime.datetime.utcnow().isoformat()
            }
            
            redis_client.lpush(redis_key, json.dumps(notification_data_redis))
            redis_client.ltrim(redis_key, 0, 99)  # Keep last 100 notifications
            redis_client.expire(redis_key, 86400)  # Expire after 24 hours
            
            # Publish to WebSocket for real-time delivery
            redis_client.publish(f"notifications:{user_id}", json.dumps(notification_data_redis))
            
            logger.info(f"In-app notification sent successfully to user {user_id}")
            return True, "In-app notification sent successfully"
            
        except Exception as e:
            logger.error(f"Failed to send in-app notification: {str(e)}")
            return False, str(e)
    
    def validate_recipient(self, recipient):
        """Validate user ID"""
        return isinstance(recipient, (int, str)) and str(recipient).isdigit()

class WebhookChannel(NotificationChannel):
    """Webhook notification channel"""
    
    def __init__(self):
        super().__init__('webhook')
    
    def send(self, notification_data):
        """Send webhook notification"""
        try:
            webhook_url = notification_data['recipient']
            payload = notification_data.get('payload', {})
            headers = notification_data.get('headers', {'Content-Type': 'application/json'})
            
            # Send webhook
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook sent successfully to {webhook_url}")
                return True, "Webhook sent successfully"
            else:
                logger.error(f"Webhook failed with status {response.status_code}: {response.text}")
                return False, f"Webhook failed with status {response.status_code}"
                
        except Exception as e:
            logger.error(f"Failed to send webhook: {str(e)}")
            return False, str(e)
    
    def validate_recipient(self, recipient):
        """Validate webhook URL"""
        try:
            from urllib.parse import urlparse
            result = urlparse(recipient)
            return all([result.scheme, result.netloc])
        except:
            return False

# Initialize notification channels
notification_channels = {
    'email': EmailChannel(),
    'sms': SMSChannel(),
    'push': PushChannel(),
    'in_app': InAppChannel(),
    'webhook': WebhookChannel()
}

class NotificationService:
    """Main notification service"""
    
    def __init__(self):
        self.channels = notification_channels
        self.analytics = NotificationAnalytics()
    
    def send_notification(self, notification_request):
        """Send notification through specified channels"""
        try:
            user_id = notification_request.get('user_id')
            template_id = notification_request.get('template_id')
            channels = notification_request.get('channels', ['in_app'])
            data = notification_request.get('data', {})
            priority = notification_request.get('priority', 'normal')
            
            # Get user preferences
            user_preferences = UserPreference.get_by_user_id(user_id)
            if user_preferences:
                # Filter channels based on user preferences
                channels = [ch for ch in channels if user_preferences.is_channel_enabled(ch)]
            
            if not channels:
                return {'success': False, 'message': 'No enabled channels for user'}
            
            # Get notification template
            template = NotificationTemplate.get_by_id(template_id)
            if not template:
                return {'success': False, 'message': 'Template not found'}
            
            # Render template
            rendered_content = render_template(template, data)
            
            # Send through each channel
            results = {}
            for channel_name in channels:
                if channel_name in self.channels:
                    # Prepare notification data for channel
                    notification_data = self._prepare_notification_data(
                        channel_name, user_id, rendered_content, data
                    )
                    
                    # Send notification
                    if priority == 'urgent':
                        # Send immediately
                        success, message = self.channels[channel_name].send(notification_data)
                        results[channel_name] = {'success': success, 'message': message}
                    else:
                        # Queue for async processing
                        task = send_notification_async.delay(channel_name, notification_data)
                        results[channel_name] = {'success': True, 'task_id': task.id}
                    
                    # Track analytics
                    self.analytics.track_notification_sent(
                        user_id, channel_name, template_id, success
                    )
            
            return {'success': True, 'results': results}
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _prepare_notification_data(self, channel_name, user_id, content, data):
        """Prepare notification data for specific channel"""
        user = User.get_by_id(user_id)
        
        if channel_name == 'email':
            return {
                'recipient': user.email,
                'subject': content.get('subject', 'Notification'),
                'body': content.get('body', ''),
                'html_body': content.get('html_body'),
                'attachments': data.get('attachments', [])
            }
        elif channel_name == 'sms':
            return {
                'recipient': user.phone,
                'body': content.get('sms_body', content.get('body', ''))
            }
        elif channel_name == 'push':
            return {
                'recipient': user.fcm_token,
                'title': content.get('title', 'Notification'),
                'body': content.get('push_body', content.get('body', '')),
                'data': data
            }
        elif channel_name == 'in_app':
            return {
                'recipient': user_id,
                'title': content.get('title', 'Notification'),
                'body': content.get('body', ''),
                'data': data
            }
        elif channel_name == 'webhook':
            return {
                'recipient': data.get('webhook_url'),
                'payload': {
                    'user_id': user_id,
                    'content': content,
                    'data': data,
                    'timestamp': datetime.datetime.utcnow().isoformat()
                },
                'headers': data.get('webhook_headers', {})
            }
        
        return {}

# Initialize notification service
notification_service = NotificationService()

# Celery tasks
@celery.task
def send_notification_async(channel_name, notification_data):
    """Send notification asynchronously"""
    try:
        if channel_name in notification_channels:
            success, message = notification_channels[channel_name].send(notification_data)
            return {'success': success, 'message': message}
        else:
            return {'success': False, 'message': 'Invalid channel'}
    except Exception as e:
        logger.error(f"Async notification failed: {str(e)}")
        return {'success': False, 'message': str(e)}

@celery.task
def send_bulk_notifications(notifications):
    """Send multiple notifications in bulk"""
    results = []
    for notification in notifications:
        result = notification_service.send_notification(notification)
        results.append(result)
    return results

@celery.task
def cleanup_old_notifications():
    """Clean up old notifications"""
    try:
        # Delete notifications older than 30 days
        cutoff_date = datetime.datetime.utcnow() - timedelta(days=30)
        deleted_count = Notification.delete_older_than(cutoff_date)
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to cleanup notifications: {str(e)}")
        return 0

# REST API Endpoints
@app.route('/api/notifications/send', methods=['POST'])
@jwt_required()
def send_notification():
    """Send a notification"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['user_id', 'template_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Send notification
        result = notification_service.send_notification(data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Send notification error: {str(e)}")
        return jsonify({'error': 'Failed to send notification'}), 500

@app.route('/api/notifications/bulk', methods=['POST'])
@jwt_required()
def send_bulk_notifications_endpoint():
    """Send multiple notifications"""
    try:
        data = request.get_json()
        notifications = data.get('notifications', [])
        
        if not notifications:
            return jsonify({'error': 'No notifications provided'}), 400
        
        # Queue bulk notifications
        task = send_bulk_notifications.delay(notifications)
        
        return jsonify({
            'message': 'Bulk notifications queued',
            'task_id': task.id
        }), 202
        
    except Exception as e:
        logger.error(f"Bulk notifications error: {str(e)}")
        return jsonify({'error': 'Failed to queue bulk notifications'}), 500

@app.route('/api/notifications/user/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_notifications(user_id):
    """Get notifications for a user"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if user can access these notifications
        if current_user_id != user_id and not User.get_by_id(current_user_id).is_admin():
            return jsonify({'error': 'Access denied'}), 403
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        unread_only = request.args.get('unread_only', False, type=bool)
        
        # Get notifications
        notifications = Notification.get_by_user(
            user_id, page=page, per_page=per_page, unread_only=unread_only
        )
        
        notification_list = []
        for notification in notifications:
            notification_data = {
                'id': notification.id,
                'title': notification.title,
                'body': notification.body,
                'channel': notification.channel,
                'status': notification.status,
                'read': notification.read,
                'created_at': notification.created_at.isoformat(),
                'data': json.loads(notification.data) if notification.data else {}
            }
            notification_list.append(notification_data)
        
        return jsonify({'notifications': notification_list}), 200
        
    except Exception as e:
        logger.error(f"Get notifications error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve notifications'}), 500

@app.route('/api/notifications/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get notification
        notification = Notification.get_by_id(notification_id)
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        # Check if user owns this notification
        if notification.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Mark as read
        notification.mark_as_read()
        
        return jsonify({'message': 'Notification marked as read'}), 200
        
    except Exception as e:
        logger.error(f"Mark read error: {str(e)}")
        return jsonify({'error': 'Failed to mark notification as read'}), 500

@app.route('/api/notifications/preferences', methods=['GET'])
@jwt_required()
def get_notification_preferences():
    """Get user notification preferences"""
    try:
        user_id = get_jwt_identity()
        
        preferences = UserPreference.get_by_user_id(user_id)
        if not preferences:
            # Create default preferences
            preferences = UserPreference.create_default(user_id)
        
        return jsonify({
            'preferences': {
                'email_enabled': preferences.email_enabled,
                'sms_enabled': preferences.sms_enabled,
                'push_enabled': preferences.push_enabled,
                'in_app_enabled': preferences.in_app_enabled,
                'quiet_hours_start': preferences.quiet_hours_start,
                'quiet_hours_end': preferences.quiet_hours_end,
                'timezone': preferences.timezone
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get preferences error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve preferences'}), 500

@app.route('/api/notifications/preferences', methods=['PUT'])
@jwt_required()
def update_notification_preferences():
    """Update user notification preferences"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        preferences = UserPreference.get_by_user_id(user_id)
        if not preferences:
            preferences = UserPreference.create_default(user_id)
        
        # Update preferences
        preferences.update(data)
        
        return jsonify({'message': 'Preferences updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Update preferences error: {str(e)}")
        return jsonify({'error': 'Failed to update preferences'}), 500

@app.route('/api/notifications/templates', methods=['GET'])
@jwt_required()
def get_notification_templates():
    """Get notification templates"""
    try:
        templates = NotificationTemplate.get_all()
        
        template_list = []
        for template in templates:
            template_data = {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'channels': template.channels,
                'variables': template.variables,
                'created_at': template.created_at.isoformat()
            }
            template_list.append(template_data)
        
        return jsonify({'templates': template_list}), 200
        
    except Exception as e:
        logger.error(f"Get templates error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve templates'}), 500

@app.route('/api/notifications/templates', methods=['POST'])
@jwt_required()
def create_notification_template():
    """Create notification template"""
    try:
        current_user = User.get_by_id(get_jwt_identity())
        if not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'content']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create template
        template = NotificationTemplate.create(data)
        
        return jsonify({
            'message': 'Template created successfully',
            'template_id': template.id
        }), 201
        
    except Exception as e:
        logger.error(f"Create template error: {str(e)}")
        return jsonify({'error': 'Failed to create template'}), 500

@app.route('/api/notifications/analytics', methods=['GET'])
@jwt_required()
def get_notification_analytics():
    """Get notification analytics"""
    try:
        current_user = User.get_by_id(get_jwt_identity())
        if not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date:
            start_date = datetime.datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.datetime.fromisoformat(end_date)
        
        analytics = notification_service.analytics.get_analytics(start_date, end_date)
        
        return jsonify({'analytics': analytics}), 200
        
    except Exception as e:
        logger.error(f"Get analytics error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve analytics'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_client.ping()
        
        # Check database connection
        # This would typically check your database connection
        
        return jsonify({
            'status': 'healthy',
            'service': 'notifications',
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'channels': list(notification_channels.keys())
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has expired'}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'error': 'Invalid token'}), 401

# Background tasks
def start_background_tasks():
    """Start background tasks"""
    
    def cleanup_task():
        """Periodic cleanup task"""
        while True:
            try:
                cleanup_old_notifications.delay()
                time.sleep(86400)  # Run daily
            except Exception as e:
                logger.error(f"Cleanup task error: {str(e)}")
                time.sleep(3600)  # Wait 1 hour on error
    
    # Start cleanup task in background thread
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

if __name__ == '__main__':
    # Initialize external services
    init_external_services()
    
    # Start background tasks
    start_background_tasks()
    
    # Run the application
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 5004),
        debug=app.config.get('DEBUG', False)
    )
