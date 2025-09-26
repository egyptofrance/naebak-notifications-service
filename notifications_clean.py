#!/usr/bin/env python3
"""
Naebak Notifications Service - Simplified Version
================================================

Multi-channel notification service for the Naebak platform.
Handles email, in-app notifications, and webhooks only.
SMS and Push notifications have been removed.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import redis
import json
import uuid
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Redis client for in-app notifications
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class NotificationChannel:
    """Base class for notification channels"""
    
    def __init__(self, name):
        self.name = name
    
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
        self.smtp_server = 'localhost'
        self.smtp_port = 587
        self.from_email = 'noreply@naebak.com'
    
    def send(self, notification_data):
        """Send email notification"""
        try:
            recipient = notification_data['recipient']
            subject = notification_data['subject']
            body = notification_data['body']
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Add text body
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # For testing, just log the email
            logger.info(f"Email notification: To={recipient}, Subject={subject}")
            logger.info(f"Body: {body}")
            
            return True, "Email logged successfully"
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")
            return False, str(e)
    
    def validate_recipient(self, recipient):
        """Validate email address"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, recipient) is not None

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
            
            # Store notification in Redis
            redis_key = f"user_notifications:{user_id}"
            notification_data_redis = {
                'id': str(uuid.uuid4()),
                'title': title,
                'body': body,
                'data': data,
                'timestamp': datetime.datetime.utcnow().isoformat(),
                'read': False
            }
            
            redis_client.lpush(redis_key, json.dumps(notification_data_redis))
            redis_client.ltrim(redis_key, 0, 99)  # Keep last 100 notifications
            redis_client.expire(redis_key, 86400 * 30)  # Expire after 30 days
            
            logger.info(f"In-app notification sent to user {user_id}: {title}")
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
            
            # For testing, just log the webhook
            logger.info(f"Webhook notification: URL={webhook_url}")
            logger.info(f"Payload: {json.dumps(payload, indent=2)}")
            
            return True, "Webhook logged successfully"
                
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

# Initialize notification channels (SMS and Push removed)
notification_channels = {
    'email': EmailChannel(),
    'in_app': InAppChannel(),
    'webhook': WebhookChannel()
}

class NotificationService:
    """Main notification service"""
    
    def __init__(self):
        self.channels = notification_channels
    
    def send_notification(self, notification_request):
        """Send notification through specified channels"""
        try:
            user_id = notification_request.get('user_id')
            channels = notification_request.get('channels', ['in_app'])
            title = notification_request.get('title', 'Notification')
            body = notification_request.get('body', '')
            data = notification_request.get('data', {})
            
            # Filter out disabled channels
            available_channels = list(self.channels.keys())
            channels = [ch for ch in channels if ch in available_channels]
            
            if not channels:
                return {'success': False, 'message': 'No available channels'}
            
            # Send through each channel
            results = {}
            for channel_name in channels:
                if channel_name in self.channels:
                    # Prepare notification data for channel
                    notification_data = self._prepare_notification_data(
                        channel_name, user_id, title, body, data
                    )
                    
                    # Send notification
                    success, message = self.channels[channel_name].send(notification_data)
                    results[channel_name] = {'success': success, 'message': message}
            
            return {'success': True, 'results': results}
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _prepare_notification_data(self, channel_name, user_id, title, body, data):
        """Prepare notification data for specific channel"""
        
        if channel_name == 'email':
            return {
                'recipient': f'user{user_id}@example.com',  # Replace with actual email
                'subject': title,
                'body': body
            }
        elif channel_name == 'in_app':
            return {
                'recipient': user_id,
                'title': title,
                'body': body,
                'data': data
            }
        elif channel_name == 'webhook':
            return {
                'recipient': 'https://example.com/webhook',  # Replace with actual webhook
                'payload': {
                    'user_id': user_id,
                    'title': title,
                    'body': body,
                    'data': data,
                    'timestamp': datetime.datetime.utcnow().isoformat()
                }
            }

# Initialize service
notification_service = NotificationService()

# API Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'naebak-notifications',
        'available_channels': list(notification_channels.keys()),
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

@app.route('/send', methods=['POST'])
def send_notification():
    """Send notification endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = notification_service.send_notification(data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in send_notification: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/notifications/<user_id>', methods=['GET'])
def get_user_notifications(user_id):
    """Get notifications for a user"""
    try:
        redis_key = f"user_notifications:{user_id}"
        notifications = redis_client.lrange(redis_key, 0, -1)
        
        parsed_notifications = []
        for notif in notifications:
            try:
                parsed_notifications.append(json.loads(notif))
            except json.JSONDecodeError:
                continue
        
        return jsonify({
            'user_id': user_id,
            'notifications': parsed_notifications,
            'count': len(parsed_notifications)
        })
        
    except Exception as e:
        logger.error(f"Error getting notifications for user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/channels', methods=['GET'])
def get_available_channels():
    """Get available notification channels"""
    return jsonify({
        'channels': list(notification_channels.keys()),
        'descriptions': {
            'email': 'Email notifications via SMTP',
            'in_app': 'In-app notifications stored in Redis',
            'webhook': 'HTTP webhook notifications'
        }
    })

if __name__ == '__main__':
    logger.info("Starting Naebak Notifications Service...")
    logger.info(f"Available channels: {list(notification_channels.keys())}")
    app.run(host='0.0.0.0', port=8003, debug=True)
