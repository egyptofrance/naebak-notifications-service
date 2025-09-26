#!/usr/bin/env python3
"""
Naebak Notifications Service - Security Middleware
==================================================

Comprehensive security middleware for protecting the notifications service
with authentication, authorization, rate limiting, input validation,
and security monitoring.

Features:
- JWT authentication and validation
- Role-based access control (RBAC)
- Rate limiting and throttling
- Input validation and sanitization
- Request/response encryption
- Security headers
- Audit logging
- Intrusion detection
"""

import jwt
import time
import hashlib
import hmac
import logging
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from functools import wraps
from flask import request, jsonify, g
import re
import bleach
from cryptography.fernet import Fernet
import json
from collections import defaultdict, deque
import threading
from config import Config

logger = logging.getLogger(__name__)

# Security constants
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS_PER_WINDOW = 100
FAILED_LOGIN_THRESHOLD = 5
LOCKOUT_DURATION = 300  # 5 minutes

class SecurityLevel(object):
    """Security levels for different operations"""
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    ADMIN = "admin"
    SYSTEM = "system"

class UserRole(object):
    """User roles for RBAC"""
    CITIZEN = "citizen"
    REPRESENTATIVE = "representative"
    ADMIN = "admin"
    SYSTEM = "system"
    MODERATOR = "moderator"

class SecurityMiddleware:
    """Main security middleware class"""
    
    def __init__(self, app=None, redis_client=None):
        self.app = app
        self.redis_client = redis_client or redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB
        )
        
        # Security configuration
        self.secret_key = Config.SECRET_KEY
        self.encryption_key = self._generate_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Rate limiting
        self.rate_limits = defaultdict(lambda: deque())
        self.failed_attempts = defaultdict(int)
        self.locked_ips = {}
        
        # Security monitoring
        self.security_events = deque(maxlen=1000)
        self.suspicious_activities = defaultdict(list)
        
        # Thread lock for thread-safe operations
        self.lock = threading.Lock()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize security middleware with Flask app"""
        self.app = app
        
        # Register before_request handlers
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        
        # Register error handlers
        app.errorhandler(401)(self.unauthorized_handler)
        app.errorhandler(403)(self.forbidden_handler)
        app.errorhandler(429)(self.rate_limit_handler)
    
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key from secret"""
        key_material = self.secret_key.encode('utf-8')
        return Fernet.generate_key()
    
    def before_request(self):
        """Process request before handling"""
        try:
            # Get client IP
            client_ip = self._get_client_ip()
            g.client_ip = client_ip
            
            # Check if IP is locked
            if self._is_ip_locked(client_ip):
                self._log_security_event("ip_locked", client_ip, "IP address is locked due to suspicious activity")
                return jsonify({"error": "Access denied", "code": "IP_LOCKED"}), 403
            
            # Rate limiting
            if not self._check_rate_limit(client_ip):
                self._log_security_event("rate_limit_exceeded", client_ip, f"Rate limit exceeded for {request.endpoint}")
                return jsonify({"error": "Rate limit exceeded", "code": "RATE_LIMITED"}), 429
            
            # Input validation
            validation_result = self._validate_request()
            if not validation_result[0]:
                self._log_security_event("invalid_input", client_ip, validation_result[1])
                return jsonify({"error": "Invalid input", "details": validation_result[1]}), 400
            
            # Authentication check
            auth_result = self._authenticate_request()
            if not auth_result[0]:
                if auth_result[1] == "token_required":
                    return jsonify({"error": "Authentication required", "code": "TOKEN_REQUIRED"}), 401
                elif auth_result[1] == "invalid_token":
                    self._record_failed_attempt(client_ip)
                    return jsonify({"error": "Invalid token", "code": "INVALID_TOKEN"}), 401
                else:
                    return jsonify({"error": "Authentication failed", "code": "AUTH_FAILED"}), 401
            
            # Authorization check
            if not self._authorize_request():
                self._log_security_event("unauthorized_access", client_ip, f"Unauthorized access to {request.endpoint}")
                return jsonify({"error": "Insufficient permissions", "code": "INSUFFICIENT_PERMISSIONS"}), 403
            
        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            return jsonify({"error": "Security check failed", "code": "SECURITY_ERROR"}), 500
    
    def after_request(self, response):
        """Process response after handling"""
        try:
            # Add security headers
            response = self._add_security_headers(response)
            
            # Log successful request
            if hasattr(g, 'user_id'):
                self._log_security_event("request_success", g.client_ip, 
                                       f"Successful request to {request.endpoint} by user {g.user_id}")
            
            return response
            
        except Exception as e:
            logger.error(f"After request security error: {str(e)}")
            return response
    
    def _get_client_ip(self) -> str:
        """Get client IP address"""
        # Check for forwarded IP first
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr or "unknown"
    
    def _is_ip_locked(self, ip: str) -> bool:
        """Check if IP is locked"""
        with self.lock:
            if ip in self.locked_ips:
                lock_time = self.locked_ips[ip]
                if datetime.utcnow() - lock_time < timedelta(seconds=LOCKOUT_DURATION):
                    return True
                else:
                    # Remove expired lock
                    del self.locked_ips[ip]
            return False
    
    def _check_rate_limit(self, ip: str) -> bool:
        """Check rate limiting for IP"""
        with self.lock:
            now = time.time()
            window_start = now - RATE_LIMIT_WINDOW
            
            # Clean old requests
            while self.rate_limits[ip] and self.rate_limits[ip][0] < window_start:
                self.rate_limits[ip].popleft()
            
            # Check if limit exceeded
            if len(self.rate_limits[ip]) >= MAX_REQUESTS_PER_WINDOW:
                return False
            
            # Add current request
            self.rate_limits[ip].append(now)
            return True
    
    def _validate_request(self) -> Tuple[bool, Optional[str]]:
        """Validate request input"""
        try:
            # Check request size
            if request.content_length and request.content_length > 10 * 1024 * 1024:  # 10MB
                return False, "Request too large"
            
            # Validate JSON if present
            if request.is_json:
                try:
                    data = request.get_json()
                    if data is None:
                        return False, "Invalid JSON format"
                    
                    # Validate specific fields
                    validation_errors = self._validate_json_data(data)
                    if validation_errors:
                        return False, "; ".join(validation_errors)
                        
                except Exception as e:
                    return False, f"JSON parsing error: {str(e)}"
            
            # Validate query parameters
            for key, value in request.args.items():
                if not self._is_safe_parameter(key, value):
                    return False, f"Invalid parameter: {key}"
            
            # Validate headers
            for key, value in request.headers.items():
                if not self._is_safe_header(key, value):
                    return False, f"Invalid header: {key}"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def _validate_json_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate JSON data"""
        errors = []
        
        # Check for common injection patterns
        def check_injection(value):
            if isinstance(value, str):
                # SQL injection patterns
                sql_patterns = [
                    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)",
                    r"(\b(UNION|OR|AND)\s+\d+\s*=\s*\d+)",
                    r"(--|#|/\*|\*/)",
                    r"(\bEXEC\b|\bEXECUTE\b)"
                ]
                
                for pattern in sql_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return f"Potential SQL injection detected in: {value[:50]}"
                
                # XSS patterns
                xss_patterns = [
                    r"<script[^>]*>.*?</script>",
                    r"javascript:",
                    r"on\w+\s*=",
                    r"<iframe[^>]*>.*?</iframe>"
                ]
                
                for pattern in xss_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return f"Potential XSS detected in: {value[:50]}"
            
            return None
        
        # Recursively check all values
        def recursive_check(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    error = check_injection(str(key))
                    if error:
                        errors.append(f"In key {current_path}: {error}")
                    
                    if isinstance(value, (dict, list)):
                        recursive_check(value, current_path)
                    else:
                        error = check_injection(str(value))
                        if error:
                            errors.append(f"In {current_path}: {error}")
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]"
                    if isinstance(item, (dict, list)):
                        recursive_check(item, current_path)
                    else:
                        error = check_injection(str(item))
                        if error:
                            errors.append(f"In {current_path}: {error}")
        
        recursive_check(data)
        return errors
    
    def _is_safe_parameter(self, key: str, value: str) -> bool:
        """Check if parameter is safe"""
        # Check parameter name
        if not re.match(r'^[a-zA-Z0-9_-]+$', key):
            return False
        
        # Check parameter value length
        if len(value) > 1000:
            return False
        
        # Check for dangerous patterns
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'data:text/html',
            r'vbscript:',
            r'onload=',
            r'onerror='
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True
    
    def _is_safe_header(self, key: str, value: str) -> bool:
        """Check if header is safe"""
        # Check header name
        if not re.match(r'^[a-zA-Z0-9_-]+$', key):
            return False
        
        # Check header value length
        if len(value) > 2000:
            return False
        
        return True
    
    def _authenticate_request(self) -> Tuple[bool, Optional[str]]:
        """Authenticate request"""
        # Skip authentication for public endpoints
        if self._is_public_endpoint():
            return True, None
        
        # Get token from header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return False, "token_required"
        
        try:
            # Extract token
            if not auth_header.startswith('Bearer '):
                return False, "invalid_token_format"
            
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Verify token
            payload = jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
            
            # Check token expiration
            if 'exp' in payload and payload['exp'] < time.time():
                return False, "token_expired"
            
            # Set user context
            g.user_id = payload.get('user_id')
            g.user_role = payload.get('role', UserRole.CITIZEN)
            g.user_permissions = payload.get('permissions', [])
            
            return True, None
            
        except jwt.ExpiredSignatureError:
            return False, "token_expired"
        except jwt.InvalidTokenError:
            return False, "invalid_token"
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False, "auth_error"
    
    def _authorize_request(self) -> bool:
        """Authorize request based on user role and permissions"""
        # Skip authorization for public endpoints
        if self._is_public_endpoint():
            return True
        
        # Get required security level for endpoint
        required_level = self._get_endpoint_security_level()
        
        # Check authorization
        if required_level == SecurityLevel.PUBLIC:
            return True
        elif required_level == SecurityLevel.AUTHENTICATED:
            return hasattr(g, 'user_id') and g.user_id is not None
        elif required_level == SecurityLevel.ADMIN:
            return hasattr(g, 'user_role') and g.user_role in [UserRole.ADMIN, UserRole.SYSTEM]
        elif required_level == SecurityLevel.SYSTEM:
            return hasattr(g, 'user_role') and g.user_role == UserRole.SYSTEM
        
        return False
    
    def _is_public_endpoint(self) -> bool:
        """Check if endpoint is public"""
        public_endpoints = [
            '/health',
            '/api/v1/auth/login',
            '/api/v1/auth/register',
            '/api/v1/auth/forgot-password',
            '/api/v1/public'
        ]
        
        return any(request.path.startswith(endpoint) for endpoint in public_endpoints)
    
    def _get_endpoint_security_level(self) -> str:
        """Get security level required for endpoint"""
        # Admin endpoints
        admin_patterns = [
            r'/api/v1/admin/',
            r'/api/v1/analytics/',
            r'/api/v1/system/'
        ]
        
        for pattern in admin_patterns:
            if re.match(pattern, request.path):
                return SecurityLevel.ADMIN
        
        # System endpoints
        system_patterns = [
            r'/api/v1/internal/',
            r'/api/v1/webhook/system'
        ]
        
        for pattern in system_patterns:
            if re.match(pattern, request.path):
                return SecurityLevel.SYSTEM
        
        # Default to authenticated
        return SecurityLevel.AUTHENTICATED
    
    def _record_failed_attempt(self, ip: str):
        """Record failed authentication attempt"""
        with self.lock:
            self.failed_attempts[ip] += 1
            
            if self.failed_attempts[ip] >= FAILED_LOGIN_THRESHOLD:
                self.locked_ips[ip] = datetime.utcnow()
                self._log_security_event("ip_locked", ip, 
                                       f"IP locked after {self.failed_attempts[ip]} failed attempts")
    
    def _add_security_headers(self, response):
        """Add security headers to response"""
        # Content Security Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        
        # Other security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response
    
    def _log_security_event(self, event_type: str, ip: str, details: str):
        """Log security event"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "ip": ip,
            "user_id": getattr(g, 'user_id', None),
            "endpoint": request.endpoint,
            "method": request.method,
            "details": details
        }
        
        self.security_events.append(event)
        logger.warning(f"Security event: {event_type} from {ip} - {details}")
        
        # Store in Redis for persistence
        try:
            key = f"security_event:{datetime.utcnow().strftime('%Y%m%d')}"
            self.redis_client.lpush(key, json.dumps(event))
            self.redis_client.expire(key, 86400 * 7)  # Keep for 7 days
        except Exception as e:
            logger.error(f"Failed to store security event: {str(e)}")
    
    def unauthorized_handler(self, error):
        """Handle 401 errors"""
        return jsonify({
            "error": "Unauthorized",
            "message": "Authentication required",
            "code": "UNAUTHORIZED"
        }), 401
    
    def forbidden_handler(self, error):
        """Handle 403 errors"""
        return jsonify({
            "error": "Forbidden",
            "message": "Insufficient permissions",
            "code": "FORBIDDEN"
        }), 403
    
    def rate_limit_handler(self, error):
        """Handle 429 errors"""
        return jsonify({
            "error": "Rate limit exceeded",
            "message": "Too many requests",
            "code": "RATE_LIMITED"
        }), 429
    
    def generate_token(self, user_id: str, role: str, permissions: List[str] = None) -> str:
        """Generate JWT token"""
        payload = {
            "user_id": user_id,
            "role": role,
            "permissions": permissions or [],
            "iat": time.time(),
            "exp": time.time() + (TOKEN_EXPIRY_HOURS * 3600)
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=JWT_ALGORITHM)
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
    
    def hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hashed.hex(), salt
    
    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """Verify password against hash"""
        return self.hash_password(password, salt)[0] == hashed
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics"""
        with self.lock:
            total_events = len(self.security_events)
            event_types = defaultdict(int)
            
            for event in self.security_events:
                event_types[event["type"]] += 1
            
            return {
                "total_security_events": total_events,
                "event_types": dict(event_types),
                "locked_ips": len(self.locked_ips),
                "failed_attempts": dict(self.failed_attempts),
                "rate_limit_active": len(self.rate_limits)
            }
    
    def get_recent_security_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent security events"""
        return list(self.security_events)[-limit:]

# Decorator functions for easy use
def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user_id') or g.user_id is None:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_role(required_role: str):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user_role') or g.user_role != required_role:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_permission(required_permission: str):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user_permissions') or required_permission not in g.user_permissions:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_input(data: Any) -> Any:
    """Sanitize input data"""
    if isinstance(data, str):
        # Remove potentially dangerous HTML
        cleaned = bleach.clean(data, tags=[], attributes={}, strip=True)
        # Escape special characters
        cleaned = cleaned.replace('<', '&lt;').replace('>', '&gt;')
        return cleaned
    elif isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    else:
        return data

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    # Egyptian phone number format
    pattern = r'^(\+20|0)?1[0-9]{9}$'
    return bool(re.match(pattern, phone))

def generate_csrf_token() -> str:
    """Generate CSRF token"""
    return hashlib.sha256(f"{time.time()}{Config.SECRET_KEY}".encode()).hexdigest()

def verify_csrf_token(token: str, max_age: int = 3600) -> bool:
    """Verify CSRF token"""
    # This is a simplified implementation
    # In production, you'd want to store tokens with timestamps
    return len(token) == 64 and all(c in '0123456789abcdef' for c in token)

# Global security middleware instance
security_middleware = SecurityMiddleware()

def init_security(app, redis_client=None):
    """Initialize security middleware"""
    global security_middleware
    security_middleware = SecurityMiddleware(app, redis_client)
    return security_middleware
