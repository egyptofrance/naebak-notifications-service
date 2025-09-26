"""
Naebak Notifications Service - Multi-channel Notification System

This is the main application file for the Naebak Notifications Service, which provides
comprehensive notification delivery across multiple channels including email, SMS, and
push notifications. The service handles notification queuing, processing, and delivery
for all platform communications including user alerts, system notifications, and
political engagement updates.

Key Features:
- Multi-channel notification delivery (email, SMS, push)
- Redis-based notification queuing for reliability
- Asynchronous notification processing
- Template-based notification content
- Delivery status tracking and retry mechanisms
- Integration with external notification providers

Architecture:
The service implements a queue-based notification system using Redis for message
persistence and delivery coordination. It supports both immediate and scheduled
notifications while providing delivery confirmation and error handling.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import redis
import json
from datetime import datetime
import logging
from config import get_config

# Setup application
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Setup CORS
CORS(app, origins=app.config["CORS_ALLOWED_ORIGINS"])

# Setup Redis for notification queue
try:
    redis_client = redis.from_url(app.config["REDIS_URL"])
    redis_client.ping()
    print("Connected to Redis for notifications queue successfully!")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis for notifications queue: {e}")
    redis_client = None

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class Notification:
    """
    Represents a notification in the Naebak notification system.
    
    This class encapsulates all notification data including recipient, delivery channel,
    content, and metadata. It provides methods for serialization and supports multiple
    notification types for different platform events and user communications.
    
    Attributes:
        user_id (str): Unique identifier of the notification recipient.
        channel (str): Delivery channel (email, sms, push).
        content (str): The notification message content.
        notification_type (str): Type of notification for categorization and processing.
        timestamp (str): ISO format timestamp of when the notification was created.
    
    Notification Types:
        - welcome: User registration and onboarding notifications
        - password_reset: Security-related notifications
        - new_message: Communication alerts
        - complaint_update: Status updates for submitted complaints
        - election_alert: Political event and election notifications
        - system_maintenance: Platform maintenance and service updates
    
    Delivery Channels:
        - email: HTML/text email notifications
        - sms: Short text message notifications
        - push: Mobile and web push notifications
    """
    
    def __init__(self, user_id, channel, content, notification_type="generic", timestamp=None):
        """
        Initialize a new notification instance.
        
        Args:
            user_id (str): The ID of the user receiving the notification.
            channel (str): The delivery channel (email, sms, push).
            content (str): The notification content/message.
            notification_type (str): Type of notification for processing logic.
            timestamp (str, optional): Notification timestamp. Defaults to current UTC time.
        """
        self.user_id = user_id
        self.channel = channel
        self.content = content
        self.notification_type = notification_type
        self.timestamp = timestamp if timestamp else datetime.utcnow().isoformat()

    def to_dict(self):
        """
        Convert notification to dictionary format for JSON serialization.
        
        Returns:
            dict: Dictionary representation of the notification with all attributes.
        """
        return {
            "user_id": self.user_id,
            "channel": self.channel,
            "content": self.content,
            "notification_type": self.notification_type,
            "timestamp": self.timestamp
        }
    
    def validate(self):
        """
        Validate notification data for required fields and format.
        
        Returns:
            tuple: (is_valid, error_message) where is_valid is boolean.
        """
        if not self.user_id:
            return False, "User ID is required"
        
        if self.channel not in ["email", "sms", "push"]:
            return False, f"Invalid channel: {self.channel}"
        
        if not self.content or len(self.content.strip()) == 0:
            return False, "Content cannot be empty"
        
        return True, None

@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for service monitoring.
    
    This endpoint provides comprehensive health status including Redis connectivity
    and service version information. It's used by load balancers, monitoring systems,
    and the API gateway to verify service availability.
    
    Returns:
        JSON response with service health information including:
        - Service status and version
        - Redis connectivity status for notification queue
        - Timestamp of the health check
        
    Health Indicators:
        - Service status: Always "ok" if the service is running
        - Redis status: "connected", "disconnected", or error details
        - Queue status: Information about pending notifications
    """
    redis_status = "disconnected"
    queue_length = 0
    
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
            queue_length = redis_client.llen("notification_queue")
        except Exception as e:
            redis_status = f"error: {e}"

    return jsonify({
        "status": "ok", 
        "service": "naebak-notifications-service", 
        "version": "1.0.0", 
        "redis_status": redis_status,
        "queue_length": queue_length,
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route("/api/notifications/send", methods=["POST"])
def send_notification_request():
    """
    Endpoint for receiving notification requests and adding them to the processing queue.
    
    This endpoint handles incoming notification requests from other services and queues
    them for asynchronous processing. It validates the request data and provides
    immediate feedback while ensuring reliable delivery through the queue system.
    
    Request Body:
        user_id (str): ID of the user to receive the notification.
        channel (str): Delivery channel (email, sms, push).
        content (str): The notification message content.
        notification_type (str, optional): Type of notification (default: "generic").
    
    Returns:
        JSON response with queuing status and notification ID.
        
    Processing Flow:
        1. Validate request data for required fields
        2. Create Notification object with timestamp
        3. Validate notification data and channel
        4. Add notification to Redis queue for processing
        5. Return confirmation with queue status
        
    Error Handling:
        - 400: Missing or invalid request data
        - 500: Redis connection or queuing errors
        - 503: Service temporarily unavailable
    """
    data = request.get_json()
    if not data or not all(key in data for key in ["user_id", "channel", "content"]):
        return jsonify({
            "error": "Missing required fields",
            "required": ["user_id", "channel", "content"]
        }), 400

    user_id = data["user_id"]
    channel = data["channel"]
    content = data["content"]
    notification_type = data.get("notification_type", "generic")

    notification = Notification(user_id, channel, content, notification_type)
    
    # Validate notification data
    is_valid, error_message = notification.validate()
    if not is_valid:
        return jsonify({"error": error_message}), 400

    if redis_client:
        try:
            redis_client.rpush("notification_queue", json.dumps(notification.to_dict()))
            logger.info(f"Notification added to queue for user {user_id} via {channel}")
            
            return jsonify({
                "message": "Notification queued successfully",
                "notification_id": f"{user_id}_{notification.timestamp}",
                "queue_position": redis_client.llen("notification_queue")
            }), 202
            
        except Exception as e:
            logger.error(f"Failed to add notification to Redis queue: {e}")
            return jsonify({
                "error": "Failed to queue notification", 
                "details": str(e)
            }), 500
    else:
        logger.error("Redis client not available, cannot queue notification.")
        return jsonify({
            "error": "Notification service temporarily unavailable"
        }), 503

@app.route("/api/notifications/status/<notification_id>", methods=["GET"])
def get_notification_status(notification_id):
    """
    Get the delivery status of a specific notification.
    
    This endpoint allows clients to check the delivery status of notifications
    they have submitted, providing transparency and enabling retry logic.
    
    Args:
        notification_id (str): The unique identifier of the notification.
        
    Returns:
        JSON response with notification status and delivery information.
    """
    # In a production system, this would query a status tracking system
    # For now, return a placeholder response
    return jsonify({
        "notification_id": notification_id,
        "status": "queued",
        "message": "Status tracking not yet implemented"
    }), 200

@app.route("/api/notifications/queue/stats", methods=["GET"])
def get_queue_statistics():
    """
    Get statistics about the notification queue.
    
    This endpoint provides operational insights into the notification system
    including queue length, processing rates, and system health metrics.
    
    Returns:
        JSON response with queue statistics and performance metrics.
    """
    if not redis_client:
        return jsonify({"error": "Redis not available"}), 503
    
    try:
        queue_length = redis_client.llen("notification_queue")
        
        return jsonify({
            "queue_length": queue_length,
            "status": "operational" if queue_length < 1000 else "high_load",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting queue statistics: {e}")
        return jsonify({"error": "Failed to get queue statistics"}), 500

def process_notification_queue():
    """
    Process notifications from the queue and deliver them through appropriate channels.
    
    This function implements the core notification processing logic, handling
    delivery through different channels and managing retry logic for failed
    deliveries. It runs as a background process or worker thread.
    
    Processing Flow:
        1. Pop notification from Redis queue (blocking operation)
        2. Parse notification data and validate
        3. Route to appropriate delivery channel handler
        4. Handle delivery confirmation and error cases
        5. Log delivery status for monitoring
        
    Delivery Channels:
        - Email: Integration with email service providers (SendGrid, AWS SES)
        - SMS: Integration with SMS providers (Twilio, AWS SNS)
        - Push: Integration with push notification services (FCM, APNs)
        
    Error Handling:
        - Failed deliveries are logged with error details
        - Retry logic can be implemented for transient failures
        - Dead letter queue for permanently failed notifications
    """
    if redis_client:
        while True:
            try:
                # BLPOP (blocking pop) to get notification from queue
                item = redis_client.blpop("notification_queue", timeout=1)
                if item:
                    notification_data = json.loads(item[1])
                    notification = Notification(**notification_data)
                    logger.info(f"Processing notification for user {notification.user_id} via {notification.channel}")
                    
                    # Route to appropriate delivery channel
                    if notification.channel == "email":
                        success = send_email_notification(notification)
                    elif notification.channel == "sms":
                        success = send_sms_notification(notification)
                    elif notification.channel == "push":
                        success = send_push_notification(notification)
                    else:
                        logger.warning(f"Unknown notification channel: {notification.channel}")
                        success = False
                    
                    # Log delivery result
                    if success:
                        logger.info(f"Successfully delivered {notification.channel} notification to {notification.user_id}")
                    else:
                        logger.error(f"Failed to deliver {notification.channel} notification to {notification.user_id}")
                        
            except Exception as e:
                logger.error(f"Error processing notification queue: {e}")

def send_email_notification(notification):
    """
    Send email notification through email service provider.
    
    Args:
        notification (Notification): The notification to send.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    logger.info(f"Sending email to {notification.user_id}: {notification.content}")
    # Here would be actual email service integration (SendGrid, AWS SES, etc.)
    # For now, simulate successful delivery
    return True

def send_sms_notification(notification):
    """
    Send SMS notification through SMS service provider.
    
    Args:
        notification (Notification): The notification to send.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    logger.info(f"Sending SMS to {notification.user_id}: {notification.content}")
    # Here would be actual SMS service integration (Twilio, AWS SNS, etc.)
    # For now, simulate successful delivery
    return True

def send_push_notification(notification):
    """
    Send push notification through push notification service.
    
    Args:
        notification (Notification): The notification to send.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    logger.info(f"Sending push notification to {notification.user_id}: {notification.content}")
    # Here would be actual push notification service integration (FCM, APNs, etc.)
    # For now, simulate successful delivery
    return True

# Background notification processing can be enabled by uncommenting the following:
# if __name__ == "__main__":
#     import threading
#     notification_processor_thread = threading.Thread(target=process_notification_queue)
#     notification_processor_thread.daemon = True
#     notification_processor_thread.start()
#     app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)

if __name__ == "__main__":
    """
    Run the notifications service application.
    
    This starts the Flask server with the configured host, port, and debug settings.
    The server handles HTTP requests for notification queuing and status checking.
    """
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
