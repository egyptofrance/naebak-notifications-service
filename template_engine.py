#!/usr/bin/env python3
"""
Naebak Notifications Service - Template Engine
==============================================

Advanced template engine for rendering notification content with support
for multiple formats, Arabic language, dynamic content, and conditional logic.

Features:
- Multi-format templates (HTML, text, JSON)
- Arabic language support with RTL
- Variable substitution and formatting
- Conditional logic and loops
- Template inheritance
- Localization support
- Rich content formatting
- Security and sanitization
"""

import re
import json
import html
import datetime
from typing import Dict, Any, List, Optional, Union
from jinja2 import Environment, BaseLoader, select_autoescape, TemplateError
from jinja2.sandbox import SandboxedEnvironment
from babel import Locale
from babel.dates import format_datetime, format_date, format_time
from babel.numbers import format_number, format_currency
import bleach
import logging

logger = logging.getLogger(__name__)

class TemplateLoader(BaseLoader):
    """Custom template loader for notification templates"""
    
    def __init__(self, templates: Dict[str, str] = None):
        self.templates = templates or {}
    
    def get_source(self, environment, template):
        if template not in self.templates:
            raise TemplateError(f"Template '{template}' not found")
        
        source = self.templates[template]
        return source, None, lambda: True
    
    def add_template(self, name: str, content: str):
        """Add a template to the loader"""
        self.templates[name] = content
    
    def remove_template(self, name: str):
        """Remove a template from the loader"""
        self.templates.pop(name, None)

class NotificationTemplateEngine:
    """Main template engine for notifications"""
    
    def __init__(self):
        self.loader = TemplateLoader()
        self.env = SandboxedEnvironment(
            loader=self.loader,
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters and functions
        self._setup_custom_filters()
        self._setup_global_functions()
        
        # Default templates
        self._load_default_templates()
    
    def _setup_custom_filters(self):
        """Setup custom Jinja2 filters"""
        
        @self.env.filter('arabic_format')
        def arabic_format(value):
            """Format text for Arabic display"""
            if not value:
                return ""
            
            # Ensure proper RTL formatting
            return f'<span dir="rtl">{html.escape(str(value))}</span>'
        
        @self.env.filter('format_datetime')
        def format_datetime_filter(value, format='medium', locale='ar'):
            """Format datetime with locale support"""
            if not value:
                return ""
            
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except:
                    return value
            
            try:
                return format_datetime(value, format=format, locale=locale)
            except:
                return str(value)
        
        @self.env.filter('format_date')
        def format_date_filter(value, format='medium', locale='ar'):
            """Format date with locale support"""
            if not value:
                return ""
            
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value).date()
                except:
                    return value
            
            try:
                return format_date(value, format=format, locale=locale)
            except:
                return str(value)
        
        @self.env.filter('format_number')
        def format_number_filter(value, locale='ar'):
            """Format number with locale support"""
            if value is None:
                return ""
            
            try:
                return format_number(float(value), locale=locale)
            except:
                return str(value)
        
        @self.env.filter('format_currency')
        def format_currency_filter(value, currency='EGP', locale='ar'):
            """Format currency with locale support"""
            if value is None:
                return ""
            
            try:
                return format_currency(float(value), currency, locale=locale)
            except:
                return str(value)
        
        @self.env.filter('truncate_words')
        def truncate_words(value, length=50, end='...'):
            """Truncate text to specified number of words"""
            if not value:
                return ""
            
            words = str(value).split()
            if len(words) <= length:
                return str(value)
            
            return ' '.join(words[:length]) + end
        
        @self.env.filter('sanitize_html')
        def sanitize_html(value):
            """Sanitize HTML content"""
            if not value:
                return ""
            
            allowed_tags = [
                'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'span', 'div',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li',
                'a', 'img'
            ]
            
            allowed_attributes = {
                'a': ['href', 'title'],
                'img': ['src', 'alt', 'width', 'height'],
                'span': ['style', 'class'],
                'div': ['style', 'class']
            }
            
            return bleach.clean(
                str(value),
                tags=allowed_tags,
                attributes=allowed_attributes,
                strip=True
            )
        
        @self.env.filter('to_json')
        def to_json(value):
            """Convert value to JSON string"""
            try:
                return json.dumps(value, ensure_ascii=False, indent=2)
            except:
                return str(value)
        
        @self.env.filter('from_json')
        def from_json(value):
            """Parse JSON string to object"""
            if not value:
                return {}
            
            try:
                return json.loads(str(value))
            except:
                return {}
        
        @self.env.filter('capitalize_arabic')
        def capitalize_arabic(value):
            """Capitalize Arabic text properly"""
            if not value:
                return ""
            
            # Simple Arabic capitalization (first letter of each word)
            words = str(value).split()
            capitalized_words = []
            
            for word in words:
                if word:
                    # For Arabic text, we don't change case but can add formatting
                    capitalized_words.append(word)
            
            return ' '.join(capitalized_words)
        
        @self.env.filter('highlight')
        def highlight(value, search_term):
            """Highlight search terms in text"""
            if not value or not search_term:
                return str(value)
            
            highlighted = re.sub(
                f'({re.escape(str(search_term))})',
                r'<mark>\1</mark>',
                str(value),
                flags=re.IGNORECASE
            )
            
            return highlighted
    
    def _setup_global_functions(self):
        """Setup global template functions"""
        
        def now():
            """Get current datetime"""
            return datetime.datetime.utcnow()
        
        def today():
            """Get current date"""
            return datetime.date.today()
        
        def url_for(endpoint, **values):
            """Generate URL for endpoint (placeholder)"""
            # In a real application, this would integrate with Flask's url_for
            base_url = "https://naebak.com"
            if endpoint == 'complaint_details':
                return f"{base_url}/complaints/{values.get('id', '')}"
            elif endpoint == 'user_profile':
                return f"{base_url}/users/{values.get('id', '')}"
            elif endpoint == 'chat':
                return f"{base_url}/chat/{values.get('id', '')}"
            else:
                return f"{base_url}/{endpoint}"
        
        def asset_url(filename):
            """Generate asset URL"""
            return f"https://cdn.naebak.com/assets/{filename}"
        
        def get_user_name(user_id):
            """Get user name by ID (placeholder)"""
            # In a real application, this would query the database
            return f"User {user_id}"
        
        def get_complaint_title(complaint_id):
            """Get complaint title by ID (placeholder)"""
            # In a real application, this would query the database
            return f"Complaint #{complaint_id}"
        
        # Add functions to template environment
        self.env.globals.update({
            'now': now,
            'today': today,
            'url_for': url_for,
            'asset_url': asset_url,
            'get_user_name': get_user_name,
            'get_complaint_title': get_complaint_title
        })
    
    def _load_default_templates(self):
        """Load default notification templates"""
        
        # Welcome message template
        welcome_template = """
        <div dir="rtl" style="font-family: 'Cairo', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <img src="{{ asset_url('logo.png') }}" alt="نائبك" style="max-width: 150px;">
            </div>
            
            <h1 style="color: #2c5aa0; text-align: center; margin-bottom: 30px;">
                مرحباً بك في منصة نائبك
            </h1>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 15px;">
                    عزيزي/عزيزتي <strong>{{ user_name | arabic_format }}</strong>،
                </p>
                
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 15px;">
                    نرحب بك في منصة نائبك، المنصة الرسمية للتواصل مع النواب والمسؤولين.
                    يمكنك الآن تقديم شكاواك واقتراحاتك بسهولة ومتابعة حالتها.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ url_for('dashboard') }}" 
                       style="background: #2c5aa0; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        ابدأ الآن
                    </a>
                </div>
            </div>
            
            <div style="border-top: 1px solid #eee; padding-top: 20px; text-align: center; color: #666;">
                <p>تم إرسال هذه الرسالة في {{ now() | format_datetime('full', 'ar') }}</p>
                <p>منصة نائبك - خدمة المواطنين</p>
            </div>
        </div>
        """
        
        # Complaint status update template
        complaint_update_template = """
        <div dir="rtl" style="font-family: 'Cairo', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <img src="{{ asset_url('logo.png') }}" alt="نائبك" style="max-width: 150px;">
            </div>
            
            <h1 style="color: #2c5aa0; text-align: center; margin-bottom: 30px;">
                تحديث حالة الشكوى
            </h1>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 15px;">
                    عزيزي/عزيزتي <strong>{{ user_name | arabic_format }}</strong>،
                </p>
                
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 15px;">
                    تم تحديث حالة شكواك رقم <strong>#{{ complaint_id }}</strong>
                </p>
                
                <div style="background: white; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #2c5aa0; margin-bottom: 10px;">تفاصيل الشكوى:</h3>
                    <p><strong>العنوان:</strong> {{ complaint_title | arabic_format }}</p>
                    <p><strong>الحالة الجديدة:</strong> 
                        <span style="background: {% if status == 'resolved' %}#28a745{% elif status == 'in_progress' %}#ffc107{% else %}#6c757d{% endif %}; 
                                     color: white; padding: 3px 8px; border-radius: 3px;">
                            {{ status_text | arabic_format }}
                        </span>
                    </p>
                    {% if response_message %}
                    <p><strong>رد المسؤول:</strong></p>
                    <div style="background: #e9ecef; padding: 10px; border-radius: 3px; margin-top: 10px;">
                        {{ response_message | arabic_format | sanitize_html }}
                    </div>
                    {% endif %}
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ url_for('complaint_details', id=complaint_id) }}" 
                       style="background: #2c5aa0; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        عرض تفاصيل الشكوى
                    </a>
                </div>
            </div>
            
            <div style="border-top: 1px solid #eee; padding-top: 20px; text-align: center; color: #666;">
                <p>تم إرسال هذه الرسالة في {{ now() | format_datetime('full', 'ar') }}</p>
                <p>منصة نائبك - خدمة المواطنين</p>
            </div>
        </div>
        """
        
        # New message notification template
        message_notification_template = """
        <div dir="rtl" style="font-family: 'Cairo', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <img src="{{ asset_url('logo.png') }}" alt="نائبك" style="max-width: 150px;">
            </div>
            
            <h1 style="color: #2c5aa0; text-align: center; margin-bottom: 30px;">
                رسالة جديدة
            </h1>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 15px;">
                    عزيزي/عزيزتي <strong>{{ recipient_name | arabic_format }}</strong>،
                </p>
                
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 15px;">
                    لديك رسالة جديدة من <strong>{{ sender_name | arabic_format }}</strong>
                </p>
                
                <div style="background: white; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #2c5aa0;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6;">
                        {{ message_preview | arabic_format | truncate_words(30) }}
                    </p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ url_for('chat', id=chat_id) }}" 
                       style="background: #2c5aa0; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        قراءة الرسالة
                    </a>
                </div>
            </div>
            
            <div style="border-top: 1px solid #eee; padding-top: 20px; text-align: center; color: #666;">
                <p>تم إرسال هذه الرسالة في {{ now() | format_datetime('full', 'ar') }}</p>
                <p>منصة نائبك - خدمة المواطنين</p>
            </div>
        </div>
        """
        
        # SMS templates (shorter format)
        sms_welcome_template = """
        مرحباً {{ user_name }}! أهلاً بك في منصة نائبك. يمكنك الآن تقديم شكاواك ومتابعتها. {{ url_for('dashboard') }}
        """
        
        sms_complaint_update_template = """
        تحديث شكوى #{{ complaint_id }}: {{ status_text }}. {{ url_for('complaint_details', id=complaint_id) }}
        """
        
        sms_message_notification_template = """
        رسالة جديدة من {{ sender_name }}: {{ message_preview | truncate_words(10) }}. {{ url_for('chat', id=chat_id) }}
        """
        
        # Push notification templates (JSON format)
        push_welcome_template = """
        {
            "title": "مرحباً بك في نائبك",
            "body": "أهلاً {{ user_name }}! يمكنك الآن تقديم شكاواك ومتابعتها",
            "icon": "{{ asset_url('icon.png') }}",
            "click_action": "{{ url_for('dashboard') }}"
        }
        """
        
        push_complaint_update_template = """
        {
            "title": "تحديث الشكوى #{{ complaint_id }}",
            "body": "{{ status_text }}: {{ complaint_title | truncate_words(8) }}",
            "icon": "{{ asset_url('icon.png') }}",
            "click_action": "{{ url_for('complaint_details', id=complaint_id) }}"
        }
        """
        
        push_message_notification_template = """
        {
            "title": "رسالة من {{ sender_name }}",
            "body": "{{ message_preview | truncate_words(10) }}",
            "icon": "{{ asset_url('icon.png') }}",
            "click_action": "{{ url_for('chat', id=chat_id) }}"
        }
        """
        
        # Add templates to loader
        templates = {
            'welcome_email': welcome_template,
            'complaint_update_email': complaint_update_template,
            'message_notification_email': message_notification_template,
            'welcome_sms': sms_welcome_template,
            'complaint_update_sms': sms_complaint_update_template,
            'message_notification_sms': sms_message_notification_template,
            'welcome_push': push_welcome_template,
            'complaint_update_push': push_complaint_update_template,
            'message_notification_push': push_message_notification_template
        }
        
        for name, content in templates.items():
            self.loader.add_template(name, content)
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with given context"""
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except TemplateError as e:
            logger.error(f"Template rendering error for '{template_name}': {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error rendering template '{template_name}': {str(e)}")
            raise TemplateError(f"Failed to render template: {str(e)}")
    
    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """Render a template string with given context"""
        try:
            template = self.env.from_string(template_string)
            return template.render(**context)
        except TemplateError as e:
            logger.error(f"String template rendering error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error rendering string template: {str(e)}")
            raise TemplateError(f"Failed to render template string: {str(e)}")
    
    def add_template(self, name: str, content: str):
        """Add a new template"""
        self.loader.add_template(name, content)
    
    def remove_template(self, name: str):
        """Remove a template"""
        self.loader.remove_template(name)
    
    def validate_template(self, template_string: str) -> Tuple[bool, Optional[str]]:
        """Validate template syntax"""
        try:
            self.env.from_string(template_string)
            return True, None
        except TemplateError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def get_template_variables(self, template_string: str) -> List[str]:
        """Extract variables from template string"""
        try:
            ast = self.env.parse(template_string)
            variables = set()
            
            def extract_variables(node):
                if hasattr(node, 'name') and isinstance(node.name, str):
                    variables.add(node.name)
                if hasattr(node, 'iter_child_nodes'):
                    for child in node.iter_child_nodes():
                        extract_variables(child)
            
            extract_variables(ast)
            return list(variables)
        except Exception as e:
            logger.error(f"Failed to extract variables: {str(e)}")
            return []

# Global template engine instance
template_engine = NotificationTemplateEngine()

def render_template(template_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
    """
    Render notification template for all channels
    
    Args:
        template_data: Template configuration with content for different channels
        context: Variables to substitute in templates
    
    Returns:
        Dictionary with rendered content for each channel
    """
    rendered_content = {}
    
    try:
        # Render email content
        if 'email' in template_data:
            email_template = template_data['email']
            if isinstance(email_template, dict):
                rendered_content['subject'] = template_engine.render_string(
                    email_template.get('subject', ''), context
                )
                rendered_content['body'] = template_engine.render_string(
                    email_template.get('body', ''), context
                )
                if 'html_body' in email_template:
                    rendered_content['html_body'] = template_engine.render_string(
                        email_template['html_body'], context
                    )
            else:
                rendered_content['body'] = template_engine.render_string(email_template, context)
        
        # Render SMS content
        if 'sms' in template_data:
            rendered_content['sms_body'] = template_engine.render_string(
                template_data['sms'], context
            )
        
        # Render push notification content
        if 'push' in template_data:
            push_template = template_data['push']
            if isinstance(push_template, dict):
                rendered_content['title'] = template_engine.render_string(
                    push_template.get('title', ''), context
                )
                rendered_content['push_body'] = template_engine.render_string(
                    push_template.get('body', ''), context
                )
            else:
                # Assume it's JSON template
                push_json = template_engine.render_string(push_template, context)
                try:
                    push_data = json.loads(push_json)
                    rendered_content['title'] = push_data.get('title', '')
                    rendered_content['push_body'] = push_data.get('body', '')
                except json.JSONDecodeError:
                    rendered_content['push_body'] = push_json
        
        # Render in-app notification content
        if 'in_app' in template_data:
            in_app_template = template_data['in_app']
            if isinstance(in_app_template, dict):
                rendered_content['title'] = template_engine.render_string(
                    in_app_template.get('title', ''), context
                )
                rendered_content['body'] = template_engine.render_string(
                    in_app_template.get('body', ''), context
                )
            else:
                rendered_content['body'] = template_engine.render_string(in_app_template, context)
        
        # Use fallback content if specific channel content not available
        if 'body' not in rendered_content and 'content' in template_data:
            rendered_content['body'] = template_engine.render_string(
                template_data['content'], context
            )
        
        if 'title' not in rendered_content and 'title' in template_data:
            rendered_content['title'] = template_engine.render_string(
                template_data['title'], context
            )
        
        return rendered_content
        
    except Exception as e:
        logger.error(f"Failed to render template: {str(e)}")
        # Return fallback content
        return {
            'title': context.get('title', 'إشعار'),
            'body': context.get('message', 'لديك إشعار جديد'),
            'subject': context.get('subject', 'إشعار من منصة نائبك')
        }

def create_template_from_type(notification_type: str, context: Dict[str, Any]) -> Dict[str, str]:
    """
    Create template content based on notification type
    
    Args:
        notification_type: Type of notification (welcome, complaint_update, etc.)
        context: Context variables
    
    Returns:
        Rendered template content
    """
    template_mapping = {
        'welcome': {
            'email': 'welcome_email',
            'sms': 'welcome_sms',
            'push': 'welcome_push'
        },
        'complaint_update': {
            'email': 'complaint_update_email',
            'sms': 'complaint_update_sms',
            'push': 'complaint_update_push'
        },
        'message_notification': {
            'email': 'message_notification_email',
            'sms': 'message_notification_sms',
            'push': 'message_notification_push'
        }
    }
    
    templates = template_mapping.get(notification_type, {})
    rendered_content = {}
    
    for channel, template_name in templates.items():
        try:
            if channel == 'email':
                content = template_engine.render_template(template_name, context)
                rendered_content['html_body'] = content
                # Extract text version (simplified)
                import re
                text_content = re.sub(r'<[^>]+>', '', content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                rendered_content['body'] = text_content
                rendered_content['subject'] = f"إشعار من منصة نائبك - {context.get('title', '')}"
            
            elif channel == 'sms':
                rendered_content['sms_body'] = template_engine.render_template(template_name, context)
            
            elif channel == 'push':
                push_json = template_engine.render_template(template_name, context)
                try:
                    push_data = json.loads(push_json)
                    rendered_content['title'] = push_data.get('title', '')
                    rendered_content['push_body'] = push_data.get('body', '')
                except json.JSONDecodeError:
                    rendered_content['push_body'] = push_json
                    
        except Exception as e:
            logger.error(f"Failed to render {channel} template for {notification_type}: {str(e)}")
    
    return rendered_content

# Utility functions
def escape_html(text: str) -> str:
    """Escape HTML characters"""
    return html.escape(str(text))

def strip_html(text: str) -> str:
    """Strip HTML tags from text"""
    import re
    clean = re.compile('<.*?>')
    return re.sub(clean, '', str(text))

def format_arabic_text(text: str) -> str:
    """Format text for proper Arabic display"""
    if not text:
        return ""
    
    # Add RTL mark for proper display
    return f"\u202B{text}\u202C"

def validate_template_syntax(template_string: str) -> Tuple[bool, Optional[str]]:
    """Validate Jinja2 template syntax"""
    return template_engine.validate_template(template_string)

def extract_template_variables(template_string: str) -> List[str]:
    """Extract variables from template"""
    return template_engine.get_template_variables(template_string)
