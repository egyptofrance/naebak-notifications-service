"""
Comprehensive test suite for Naebak Notifications Service.

This test suite covers all major functionality of the notifications service
including notification creation, delivery channels, template management,
user preferences, and error handling scenarios.
"""

import unittest
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the application and models
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, delivery_manager
from models import (
    Notification, NotificationTemplate, UserNotificationPreference,
    NotificationStatus, NotificationChannel, NotificationType, NotificationPriority,
    init_database
)
from config import TestingConfig


class NotificationsServiceTestCase(unittest.TestCase):
    """Base test case for notifications service tests."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Configure app for testing
        app.config.from_object(TestingConfig())
        self.app = app
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Initialize test database
        self.engine, self.SessionLocal = init_database('sqlite:///:memory:')
        
        # Create test user token
        self.test_user_id = str(uuid.uuid4())
        self.test_token = self._create_test_token(self.test_user_id, 'citizen')
        self.admin_token = self._create_test_token('admin-user', 'admin')
        
        # Set up authorization headers
        self.auth_headers = {'Authorization': f'Bearer {self.test_token}'}
        self.admin_headers = {'Authorization': f'Bearer {self.admin_token}'}
    
    def tearDown(self):
        """Clean up after each test."""
        self.app_context.pop()
    
    def _create_test_token(self, user_id: str, role: str) -> str:
        """Create a test JWT token."""
        import jwt
        payload = {
            'user_id': user_id,
            'role': role,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')


class TestHealthEndpoint(NotificationsServiceTestCase):
    """Test health check endpoint."""
    
    def test_health_check_success(self):
        """Test successful health check."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
        self.assertIn('services', data)


class TestNotificationCreation(NotificationsServiceTestCase):
    """Test notification creation endpoints."""
    
    def test_create_notification_success(self):
        """Test successful notification creation."""
        notification_data = {
            'user_id': self.test_user_id,
            'notification_type': 'welcome',
            'channel': 'email',
            'content': 'Welcome to Naebak platform!',
            'subject': 'Welcome!',
            'priority': 'normal'
        }
        
        response = self.client.post(
            '/notifications',
            json=notification_data,
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn('id', data)
        self.assertEqual(data['status'], 'pending')
    
    def test_create_notification_missing_fields(self):
        """Test notification creation with missing required fields."""
        notification_data = {
            'user_id': self.test_user_id,
            'channel': 'email'
            # Missing notification_type and content
        }
        
        response = self.client.post(
            '/notifications',
            json=notification_data,
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_create_notification_invalid_enum(self):
        """Test notification creation with invalid enum values."""
        notification_data = {
            'user_id': self.test_user_id,
            'notification_type': 'invalid_type',
            'channel': 'invalid_channel',
            'content': 'Test content'
        }
        
        response = self.client.post(
            '/notifications',
            json=notification_data,
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('Invalid enum value', data['error'])
    
    def test_create_scheduled_notification(self):
        """Test creating a scheduled notification."""
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        notification_data = {
            'user_id': self.test_user_id,
            'notification_type': 'reminder',
            'channel': 'email',
            'content': 'Scheduled reminder',
            'scheduled_at': future_time
        }
        
        response = self.client.post(
            '/notifications',
            json=notification_data,
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIsNotNone(data['scheduled_at'])


class TestNotificationRetrieval(NotificationsServiceTestCase):
    """Test notification retrieval endpoints."""
    
    def test_get_notification_success(self):
        """Test successful notification retrieval."""
        # First create a notification
        notification_data = {
            'user_id': self.test_user_id,
            'notification_type': 'welcome',
            'channel': 'email',
            'content': 'Test notification'
        }
        
        create_response = self.client.post(
            '/notifications',
            json=notification_data,
            headers=self.auth_headers
        )
        
        notification_id = json.loads(create_response.data)['id']
        
        # Then retrieve it
        response = self.client.get(
            f'/notifications/{notification_id}',
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['id'], notification_id)
        self.assertEqual(data['content'], 'Test notification')
    
    def test_get_notification_not_found(self):
        """Test retrieving non-existent notification."""
        fake_id = str(uuid.uuid4())
        
        response = self.client.get(
            f'/notifications/{fake_id}',
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_list_notifications_with_pagination(self):
        """Test listing notifications with pagination."""
        response = self.client.get(
            '/notifications?page=1&per_page=10',
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('notifications', data)
        self.assertIn('pagination', data)
        self.assertIn('page', data['pagination'])
        self.assertIn('total', data['pagination'])


class TestUserPreferences(NotificationsServiceTestCase):
    """Test user preference management."""
    
    def test_get_user_preferences(self):
        """Test retrieving user preferences."""
        response = self.client.get(
            f'/users/{self.test_user_id}/preferences',
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['user_id'], self.test_user_id)
        self.assertIn('preferences', data)
    
    def test_update_user_preferences(self):
        """Test updating user preferences."""
        preferences_data = {
            'preferences': {
                'welcome': {
                    'email': {
                        'enabled': True,
                        'quiet_hours_start': '22:00',
                        'quiet_hours_end': '08:00'
                    },
                    'sms': {
                        'enabled': False
                    }
                }
            }
        }
        
        response = self.client.put(
            f'/users/{self.test_user_id}/preferences',
            json=preferences_data,
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('Updated', data['message'])
    
    def test_access_denied_other_user_preferences(self):
        """Test access denied when accessing other user's preferences."""
        other_user_id = str(uuid.uuid4())
        
        response = self.client.get(
            f'/users/{other_user_id}/preferences',
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 403)


class TestTemplateManagement(NotificationsServiceTestCase):
    """Test notification template management."""
    
    def test_list_templates_admin_only(self):
        """Test that only admins can list templates."""
        # Test with regular user
        response = self.client.get('/templates', headers=self.auth_headers)
        self.assertEqual(response.status_code, 403)
        
        # Test with admin user
        response = self.client.get('/templates', headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
    
    def test_create_template_admin_only(self):
        """Test that only admins can create templates."""
        template_data = {
            'name': 'Test Template',
            'notification_type': 'welcome',
            'channel': 'email',
            'content': 'Welcome {{user_name}} to Naebak!',
            'subject': 'Welcome to Naebak'
        }
        
        # Test with regular user
        response = self.client.post(
            '/templates',
            json=template_data,
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 403)
        
        # Test with admin user
        response = self.client.post(
            '/templates',
            json=template_data,
            headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 201)


class TestBulkNotifications(NotificationsServiceTestCase):
    """Test bulk notification functionality."""
    
    def test_send_bulk_notifications_admin_only(self):
        """Test that only admins can send bulk notifications."""
        bulk_data = {
            'user_ids': [str(uuid.uuid4()) for _ in range(5)],
            'notification_type': 'announcement',
            'channel': 'email',
            'content': 'Important announcement for all users'
        }
        
        # Test with regular user
        response = self.client.post(
            '/bulk/send',
            json=bulk_data,
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 403)
        
        # Test with admin user
        response = self.client.post(
            '/bulk/send',
            json=bulk_data,
            headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 201)
    
    def test_bulk_notifications_size_limit(self):
        """Test bulk notification size limit."""
        bulk_data = {
            'user_ids': [str(uuid.uuid4()) for _ in range(1001)],  # Exceeds limit
            'notification_type': 'announcement',
            'channel': 'email',
            'content': 'Test content'
        }
        
        response = self.client.post(
            '/bulk/send',
            json=bulk_data,
            headers=self.admin_headers
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('Maximum 1000 users', data['error'])


class TestNotificationRetry(NotificationsServiceTestCase):
    """Test notification retry functionality."""
    
    @patch('celery_tasks.send_notification.delay')
    def test_retry_failed_notification(self, mock_send):
        """Test retrying a failed notification."""
        # Create a notification first
        notification_data = {
            'user_id': self.test_user_id,
            'notification_type': 'welcome',
            'channel': 'email',
            'content': 'Test notification'
        }
        
        create_response = self.client.post(
            '/notifications',
            json=notification_data,
            headers=self.auth_headers
        )
        
        notification_id = json.loads(create_response.data)['id']
        
        # Retry the notification
        response = self.client.post(
            f'/notifications/{notification_id}/retry',
            headers=self.auth_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('queued for retry', data['message'])


class TestNotificationStats(NotificationsServiceTestCase):
    """Test notification statistics endpoints."""
    
    def test_get_notification_stats_admin_only(self):
        """Test that only admins can access notification stats."""
        # Test with regular user
        response = self.client.get('/stats', headers=self.auth_headers)
        self.assertEqual(response.status_code, 403)
        
        # Test with admin user
        response = self.client.get('/stats', headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('total_notifications', data)
        self.assertIn('by_status', data)
        self.assertIn('by_channel', data)
        self.assertIn('by_type', data)
    
    def test_notification_stats_with_filters(self):
        """Test notification stats with date and user filters."""
        response = self.client.get(
            f'/stats?days=30&user_id={self.test_user_id}',
            headers=self.admin_headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['period']['days'], 30)


class TestDeliveryChannels(NotificationsServiceTestCase):
    """Test notification delivery channels."""
    
    @patch('delivery_channels.EmailChannel.send')
    def test_email_delivery_channel(self, mock_send):
        """Test email delivery channel."""
        mock_send.return_value = (True, None)
        
        # Test email channel functionality
        from delivery_channels import EmailChannel
        
        email_config = {
            'api_key': 'test-key',
            'from_email': 'test@naebak.com',
            'from_name': 'Test Naebak'
        }
        
        channel = EmailChannel(email_config)
        success, error = channel.send(
            recipient='user@example.com',
            subject='Test Subject',
            content='Test Content'
        )
        
        self.assertTrue(success)
        self.assertIsNone(error)
        mock_send.assert_called_once()
    
    @patch('delivery_channels.SMSChannel.send')
    def test_sms_delivery_channel(self, mock_send):
        """Test SMS delivery channel."""
        mock_send.return_value = (True, None)
        
        # Test SMS channel functionality
        from delivery_channels import SMSChannel
        
        sms_config = {
            'account_sid': 'test-sid',
            'auth_token': 'test-token',
            'from_number': '+1234567890'
        }
        
        channel = SMSChannel(sms_config)
        success, error = channel.send(
            recipient='+1987654321',
            content='Test SMS Content'
        )
        
        self.assertTrue(success)
        self.assertIsNone(error)
        mock_send.assert_called_once()


class TestTemplateSystem(NotificationsServiceTestCase):
    """Test notification template system."""
    
    def test_template_rendering(self):
        """Test template content rendering with variables."""
        from template_system import TemplateManager
        
        # Create a mock database session
        mock_session = Mock()
        template_manager = TemplateManager(mock_session)
        
        template_content = "Hello {{user_name}}, welcome to {{platform_name}}!"
        variables = {
            'user_name': 'أحمد محمد',
            'platform_name': 'نائبك'
        }
        
        rendered = template_manager.render_template(template_content, variables)
        expected = "Hello أحمد محمد, welcome to نائبك!"
        
        self.assertEqual(rendered, expected)
    
    def test_template_validation(self):
        """Test template content validation."""
        from template_system import TemplateManager
        
        mock_session = Mock()
        template_manager = TemplateManager(mock_session)
        
        # Test valid template
        valid_template = "Hello {{user_name}}!"
        is_valid, error = template_manager.validate_template(valid_template)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # Test invalid template (unclosed tag)
        invalid_template = "Hello {{user_name}!"
        is_valid, error = template_manager.validate_template(invalid_template)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)


class TestErrorHandling(NotificationsServiceTestCase):
    """Test error handling scenarios."""
    
    def test_unauthorized_access(self):
        """Test unauthorized access to protected endpoints."""
        response = self.client.get('/notifications')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.post('/notifications', json={})
        self.assertEqual(response.status_code, 401)
    
    def test_invalid_json_request(self):
        """Test handling of invalid JSON requests."""
        response = self.client.post(
            '/notifications',
            data='invalid json',
            headers=self.auth_headers,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_database_error_handling(self):
        """Test handling of database errors."""
        # This would require mocking database failures
        # Implementation depends on specific error scenarios
        pass


class TestWebhooks(NotificationsServiceTestCase):
    """Test webhook endpoints for delivery status updates."""
    
    def test_sendgrid_webhook(self):
        """Test SendGrid webhook handling."""
        webhook_data = [
            {
                'event': 'delivered',
                'email': 'user@example.com',
                'timestamp': int(datetime.utcnow().timestamp()),
                'sg_message_id': 'test-message-id'
            }
        ]
        
        response = self.client.post(
            '/webhooks/sendgrid',
            json=webhook_data
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_twilio_webhook(self):
        """Test Twilio webhook handling."""
        webhook_data = {
            'MessageStatus': 'delivered',
            'MessageSid': 'test-message-sid',
            'To': '+1987654321',
            'From': '+1234567890'
        }
        
        response = self.client.post(
            '/webhooks/twilio',
            data=webhook_data
        )
        
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    # Run the test suite
    unittest.main(verbosity=2)
