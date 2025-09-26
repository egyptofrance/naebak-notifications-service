"""
Naebak Notifications Service - Template System and User Preferences

This module implements the template rendering system and user preference management
for the notifications service. It provides flexible template-based notification
content generation with variable substitution and comprehensive user preference
management for personalized notification experiences.

Key Features:
- Jinja2-based template rendering with Arabic language support
- Variable substitution and content personalization
- User preference management across channels and notification types
- Template validation and error handling
- Caching for improved performance
- Integration with notification delivery system
"""

import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, time
import json
import re
from jinja2 import Environment, BaseLoader, Template, TemplateError
from sqlalchemy.orm import Session

# Internal imports
from models import (
    NotificationTemplate, UserNotificationPreference, 
    NotificationType, NotificationChannel, NotificationPriority
)

logger = logging.getLogger(__name__)

class TemplateRenderer:
    """
    Template rendering engine for notification content.
    
    This class handles the rendering of notification templates with variable
    substitution, supporting both Arabic and English content with proper
    formatting and validation.
    
    Features:
        - Jinja2 template engine with custom filters
        - Arabic text formatting and RTL support
        - Variable validation and type checking
        - Template caching for performance
        - Error handling and fallback content
    """
    
    def __init__(self):
        """Initialize the template renderer with Jinja2 environment."""
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters for Arabic content
        self.env.filters['arabic_number'] = self._arabic_number_filter
        self.env.filters['format_date_arabic'] = self._format_date_arabic
        self.env.filters['truncate_arabic'] = self._truncate_arabic
        
        # Template cache for performance
        self._template_cache = {}
    
    def _arabic_number_filter(self, value: Any) -> str:
        """
        Convert numbers to Arabic-Indic numerals.
        
        Args:
            value: The value to convert
            
        Returns:
            str: Value with Arabic-Indic numerals
        """
        if value is None:
            return ""
        
        arabic_digits = '٠١٢٣٤٥٦٧٨٩'
        english_digits = '0123456789'
        
        value_str = str(value)
        for eng, ara in zip(english_digits, arabic_digits):
            value_str = value_str.replace(eng, ara)
        
        return value_str
    
    def _format_date_arabic(self, date_value: datetime, format_type: str = 'full') -> str:
        """
        Format datetime for Arabic display.
        
        Args:
            date_value: The datetime to format
            format_type: Type of formatting (full, date, time)
            
        Returns:
            str: Formatted Arabic date string
        """
        if not isinstance(date_value, datetime):
            return str(date_value)
        
        arabic_months = [
            'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
            'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
        ]
        
        if format_type == 'date':
            return f"{date_value.day} {arabic_months[date_value.month - 1]} {date_value.year}"
        elif format_type == 'time':
            return f"{date_value.hour:02d}:{date_value.minute:02d}"
        else:  # full
            return f"{date_value.day} {arabic_months[date_value.month - 1]} {date_value.year} - {date_value.hour:02d}:{date_value.minute:02d}"
    
    def _truncate_arabic(self, text: str, length: int = 100, suffix: str = "...") -> str:
        """
        Truncate Arabic text while preserving word boundaries.
        
        Args:
            text: The text to truncate
            length: Maximum length
            suffix: Suffix to add if truncated
            
        Returns:
            str: Truncated text
        """
        if len(text) <= length:
            return text
        
        # Find the last space before the length limit
        truncated = text[:length]
        last_space = truncated.rfind(' ')
        
        if last_space > 0:
            truncated = truncated[:last_space]
        
        return truncated + suffix
    
    def render_template(self, template_content: str, variables: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Render a template with the provided variables.
        
        Args:
            template_content: The template content string
            variables: Dictionary of variables for substitution
            
        Returns:
            tuple: (success, rendered_content, error_message)
        """
        try:
            # Check cache first
            cache_key = hash(template_content)
            if cache_key in self._template_cache:
                template = self._template_cache[cache_key]
            else:
                template = self.env.from_string(template_content)
                self._template_cache[cache_key] = template
            
            # Render template with variables
            rendered = template.render(**variables)
            return True, rendered, None
            
        except TemplateError as e:
            logger.error(f"Template rendering error: {str(e)}")
            return False, template_content, f"Template error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected template rendering error: {str(e)}")
            return False, template_content, f"Rendering error: {str(e)}"
    
    def validate_template(self, template_content: str, required_variables: List[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate template syntax and required variables.
        
        Args:
            template_content: The template content to validate
            required_variables: List of required variable names
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Parse template to check syntax
            template = self.env.from_string(template_content)
            
            # Check for required variables if specified
            if required_variables:
                # Extract variables from template
                ast = self.env.parse(template_content)
                template_variables = set()
                
                for node in ast.find_all():
                    if hasattr(node, 'name'):
                        template_variables.add(node.name)
                
                # Check if all required variables are present
                missing_variables = set(required_variables) - template_variables
                if missing_variables:
                    return False, f"Missing required variables: {', '.join(missing_variables)}"
            
            return True, None
            
        except TemplateError as e:
            return False, f"Template syntax error: {str(e)}"
        except Exception as e:
            return False, f"Template validation error: {str(e)}"

class UserPreferenceManager:
    """
    Manager for user notification preferences and settings.
    
    This class handles the management of user-specific notification preferences,
    including channel preferences, frequency settings, quiet hours, and
    notification type filtering.
    
    Features:
        - Per-user, per-channel, per-type preference management
        - Quiet hours and timezone support
        - Frequency settings (immediate, daily, weekly)
        - Preference inheritance and defaults
        - Bulk preference operations
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize the preference manager with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all notification preferences for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            dict: Nested dictionary of preferences by type and channel
        """
        preferences = self.db_session.query(UserNotificationPreference).filter_by(
            user_id=user_id
        ).all()
        
        result = {}
        for pref in preferences:
            if pref.notification_type.value not in result:
                result[pref.notification_type.value] = {}
            
            result[pref.notification_type.value][pref.channel.value] = {
                'enabled': pref.is_enabled,
                'frequency': pref.frequency,
                'quiet_hours_start': pref.quiet_hours_start,
                'quiet_hours_end': pref.quiet_hours_end,
                'timezone': pref.timezone
            }
        
        return result
    
    def set_user_preference(self, user_id: str, notification_type: NotificationType, 
                           channel: NotificationChannel, **kwargs) -> bool:
        """
        Set a specific notification preference for a user.
        
        Args:
            user_id: ID of the user
            notification_type: Type of notification
            channel: Delivery channel
            **kwargs: Preference settings (enabled, frequency, etc.)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if preference already exists
            existing_pref = self.db_session.query(UserNotificationPreference).filter_by(
                user_id=user_id,
                notification_type=notification_type,
                channel=channel
            ).first()
            
            if existing_pref:
                # Update existing preference
                for key, value in kwargs.items():
                    if hasattr(existing_pref, key):
                        setattr(existing_pref, key, value)
                existing_pref.updated_at = datetime.utcnow()
            else:
                # Create new preference
                new_pref = UserNotificationPreference(
                    user_id=user_id,
                    notification_type=notification_type,
                    channel=channel,
                    **kwargs
                )
                self.db_session.add(new_pref)
            
            self.db_session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to set user preference: {str(e)}")
            self.db_session.rollback()
            return False
    
    def should_send_notification(self, user_id: str, notification_type: NotificationType, 
                                channel: NotificationChannel, priority: NotificationPriority = NotificationPriority.NORMAL) -> Tuple[bool, str]:
        """
        Check if a notification should be sent based on user preferences.
        
        Args:
            user_id: ID of the user
            notification_type: Type of notification
            channel: Delivery channel
            priority: Notification priority
            
        Returns:
            tuple: (should_send, reason)
        """
        # Get user preference
        preference = self.db_session.query(UserNotificationPreference).filter_by(
            user_id=user_id,
            notification_type=notification_type,
            channel=channel
        ).first()
        
        # If no preference exists, use defaults
        if not preference:
            # Default: allow all notifications except marketing
            if notification_type == NotificationType.MARKETING:
                return False, "Marketing notifications disabled by default"
            return True, "Default preference allows notification"
        
        # Check if notifications are enabled for this type/channel
        if not preference.is_enabled:
            return False, f"User disabled {notification_type.value} notifications via {channel.value}"
        
        # Urgent notifications always go through
        if priority == NotificationPriority.URGENT:
            return True, "Urgent notification overrides preferences"
        
        # Check quiet hours
        if preference.quiet_hours_start and preference.quiet_hours_end:
            current_time = datetime.now().time()
            quiet_start = time.fromisoformat(preference.quiet_hours_start)
            quiet_end = time.fromisoformat(preference.quiet_hours_end)
            
            # Handle quiet hours that span midnight
            if quiet_start <= quiet_end:
                in_quiet_hours = quiet_start <= current_time <= quiet_end
            else:
                in_quiet_hours = current_time >= quiet_start or current_time <= quiet_end
            
            if in_quiet_hours and priority != NotificationPriority.HIGH:
                return False, "Within user's quiet hours"
        
        # Check frequency settings
        if preference.frequency == 'disabled':
            return False, "Notifications disabled for this type/channel"
        elif preference.frequency in ['daily', 'weekly']:
            # For batched notifications, we'll handle this in the delivery system
            return True, f"Notification will be batched ({preference.frequency})"
        
        return True, "User preferences allow notification"
    
    def get_default_preferences(self) -> Dict[str, Dict[str, Any]]:
        """
        Get default notification preferences for new users.
        
        Returns:
            dict: Default preferences by type and channel
        """
        defaults = {}
        
        # Define default preferences
        default_settings = {
            NotificationType.WELCOME: {
                NotificationChannel.EMAIL: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.IN_APP: {'enabled': True, 'frequency': 'immediate'}
            },
            NotificationType.SECURITY: {
                NotificationChannel.EMAIL: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.SMS: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.IN_APP: {'enabled': True, 'frequency': 'immediate'}
            },
            NotificationType.MESSAGE: {
                NotificationChannel.EMAIL: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.PUSH: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.IN_APP: {'enabled': True, 'frequency': 'immediate'}
            },
            NotificationType.COMPLAINT: {
                NotificationChannel.EMAIL: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.SMS: {'enabled': False, 'frequency': 'immediate'},
                NotificationChannel.IN_APP: {'enabled': True, 'frequency': 'immediate'}
            },
            NotificationType.ELECTION: {
                NotificationChannel.EMAIL: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.PUSH: {'enabled': True, 'frequency': 'immediate'},
                NotificationChannel.IN_APP: {'enabled': True, 'frequency': 'immediate'}
            },
            NotificationType.SYSTEM: {
                NotificationChannel.EMAIL: {'enabled': True, 'frequency': 'daily'},
                NotificationChannel.IN_APP: {'enabled': True, 'frequency': 'immediate'}
            },
            NotificationType.MARKETING: {
                NotificationChannel.EMAIL: {'enabled': False, 'frequency': 'weekly'},
                NotificationChannel.PUSH: {'enabled': False, 'frequency': 'weekly'}
            }
        }
        
        # Convert to string keys for JSON serialization
        for notification_type, channels in default_settings.items():
            defaults[notification_type.value] = {}
            for channel, settings in channels.items():
                defaults[notification_type.value][channel.value] = settings
        
        return defaults
    
    def initialize_user_preferences(self, user_id: str) -> bool:
        """
        Initialize default preferences for a new user.
        
        Args:
            user_id: ID of the new user
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            defaults = self.get_default_preferences()
            
            for notification_type_str, channels in defaults.items():
                notification_type = NotificationType(notification_type_str)
                
                for channel_str, settings in channels.items():
                    channel = NotificationChannel(channel_str)
                    
                    # Create preference record
                    preference = UserNotificationPreference(
                        user_id=user_id,
                        notification_type=notification_type,
                        channel=channel,
                        is_enabled=settings['enabled'],
                        frequency=settings['frequency'],
                        timezone='UTC'  # Default timezone
                    )
                    self.db_session.add(preference)
            
            self.db_session.commit()
            logger.info(f"Initialized default preferences for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize user preferences: {str(e)}")
            self.db_session.rollback()
            return False

class TemplateManager:
    """
    Manager for notification templates and template operations.
    
    This class handles the management of notification templates including
    creation, validation, activation, and retrieval of templates for
    different notification types and channels.
    
    Features:
        - Template CRUD operations
        - Template validation and testing
        - Version management and rollback
        - Template caching and performance optimization
        - Integration with template renderer
    """
    
    def __init__(self, db_session: Session, template_renderer: TemplateRenderer):
        """
        Initialize the template manager.
        
        Args:
            db_session: SQLAlchemy database session
            template_renderer: Template rendering engine
        """
        self.db_session = db_session
        self.renderer = template_renderer
    
    def get_template(self, notification_type: NotificationType, channel: NotificationChannel) -> Optional[NotificationTemplate]:
        """
        Get the active template for a notification type and channel.
        
        Args:
            notification_type: Type of notification
            channel: Delivery channel
            
        Returns:
            NotificationTemplate: Active template or None if not found
        """
        return self.db_session.query(NotificationTemplate).filter_by(
            notification_type=notification_type,
            channel=channel,
            is_active=True
        ).first()
    
    def create_template(self, name: str, notification_type: NotificationType, 
                       channel: NotificationChannel, content: str, 
                       subject: str = None, variables: Dict[str, Any] = None,
                       created_by: str = None) -> Tuple[bool, Optional[NotificationTemplate], Optional[str]]:
        """
        Create a new notification template.
        
        Args:
            name: Template name
            notification_type: Type of notification
            channel: Delivery channel
            content: Template content
            subject: Template subject (for email)
            variables: Template variable schema
            created_by: User ID who created the template
            
        Returns:
            tuple: (success, template, error_message)
        """
        try:
            # Validate template content
            required_vars = list(variables.keys()) if variables else []
            is_valid, error_msg = self.renderer.validate_template(content, required_vars)
            
            if not is_valid:
                return False, None, f"Template validation failed: {error_msg}"
            
            # Create template
            template = NotificationTemplate(
                name=name,
                notification_type=notification_type,
                channel=channel,
                subject=subject,
                content=content,
                variables=variables or {},
                created_by=created_by
            )
            
            self.db_session.add(template)
            self.db_session.commit()
            
            logger.info(f"Created template '{name}' for {notification_type.value}/{channel.value}")
            return True, template, None
            
        except Exception as e:
            logger.error(f"Failed to create template: {str(e)}")
            self.db_session.rollback()
            return False, None, f"Template creation failed: {str(e)}"
    
    def render_notification_content(self, template: NotificationTemplate, 
                                  variables: Dict[str, Any]) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Render notification content using a template.
        
        Args:
            template: The notification template
            variables: Variables for template rendering
            
        Returns:
            tuple: (success, rendered_content, rendered_subject, error_message)
        """
        # Render content
        content_success, rendered_content, content_error = self.renderer.render_template(
            template.content, variables
        )
        
        if not content_success:
            return False, template.content, template.subject, content_error
        
        # Render subject if present
        rendered_subject = template.subject
        if template.subject:
            subject_success, rendered_subject, subject_error = self.renderer.render_template(
                template.subject, variables
            )
            if not subject_success:
                logger.warning(f"Subject rendering failed for template {template.id}: {subject_error}")
                rendered_subject = template.subject  # Fallback to original subject
        
        return True, rendered_content, rendered_subject, None
    
    def get_default_templates(self) -> Dict[str, Dict[str, str]]:
        """
        Get default templates for system initialization.
        
        Returns:
            dict: Default templates by type and channel
        """
        return {
            'welcome_email': {
                'type': 'welcome',
                'channel': 'email',
                'subject': 'مرحباً بك في منصة نائبك، {{user_name}}',
                'content': '''
                <div dir="rtl" style="font-family: Arial, sans-serif; color: #333;">
                    <h2>مرحباً بك في منصة نائبك</h2>
                    <p>عزيزي {{user_name}}،</p>
                    <p>نرحب بك في منصة نائبك، المنصة الرقمية التي تربط بين المواطنين ونوابهم في البرلمان.</p>
                    <p>يمكنك الآن:</p>
                    <ul>
                        <li>تقديم الشكاوى والاقتراحات</li>
                        <li>التواصل مع نوابك</li>
                        <li>متابعة أحدث الأخبار السياسية</li>
                        <li>المشاركة في الاستطلاعات</li>
                    </ul>
                    <p>شكراً لانضمامك إلينا!</p>
                    <p>فريق منصة نائبك</p>
                </div>
                ''',
                'variables': {'user_name': {'type': 'string', 'required': True}}
            },
            'security_sms': {
                'type': 'security',
                'channel': 'sms',
                'content': 'منصة نائبك: تم تسجيل دخول جديد إلى حسابك في {{login_time}}. إذا لم تكن أنت، يرجى تغيير كلمة المرور فوراً.',
                'variables': {'login_time': {'type': 'string', 'required': True}}
            },
            'message_push': {
                'type': 'message',
                'channel': 'push',
                'subject': 'رسالة جديدة من {{sender_name}}',
                'content': '{{message_preview}}',
                'variables': {
                    'sender_name': {'type': 'string', 'required': True},
                    'message_preview': {'type': 'string', 'required': True}
                }
            }
        }

# Factory functions
def create_template_renderer() -> TemplateRenderer:
    """Create a configured template renderer instance."""
    return TemplateRenderer()

def create_preference_manager(db_session: Session) -> UserPreferenceManager:
    """Create a user preference manager instance."""
    return UserPreferenceManager(db_session)

def create_template_manager(db_session: Session, template_renderer: TemplateRenderer = None) -> TemplateManager:
    """Create a template manager instance."""
    if template_renderer is None:
        template_renderer = create_template_renderer()
    return TemplateManager(db_session, template_renderer)
