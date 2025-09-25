from flask import Flask, request, jsonify
from flask_cors import CORS
import redis
import json
from datetime import datetime
import logging
from config import get_config

# إعداد التطبيق
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# إعداد CORS
CORS(app, origins=app.config["CORS_ALLOWED_ORIGINS"])

# إعداد Redis لقائمة الانتظار
try:
    redis_client = redis.from_url(app.config["REDIS_URL"])
    redis_client.ping()
    print("Connected to Redis for notifications queue successfully!")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis for notifications queue: {e}")
    redis_client = None

# إعداد Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# نموذج لإشعار (كما هو موضح في LEADER.md)
class Notification:
    def __init__(self, user_id, channel, content, notification_type="generic", timestamp=None):
        self.user_id = user_id
        self.channel = channel  # email, sms, push
        self.content = content
        self.notification_type = notification_type # e.g., welcome, password_reset, new_message
        self.timestamp = timestamp if timestamp else datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "channel": self.channel,
            "content": self.content,
            "notification_type": self.notification_type,
            "timestamp": self.timestamp
        }

@app.route("/health", methods=["GET"])
def health_check():
    """فحص صحة الخدمة"""
    redis_status = "disconnected"
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
        except Exception as e:
            redis_status = f"error: {e}"

    return jsonify({"status": "ok", "service": "naebak-notifications-service", "version": "1.0.0", "redis_status": redis_status}), 200

@app.route("/api/notifications/send", methods=["POST"])
def send_notification_request():
    """نقطة نهاية لتلقي طلبات الإشعارات وإضافتها إلى قائمة الانتظار"""
    data = request.get_json()
    if not data or not all(key in data for key in ["user_id", "channel", "content"]):
        return jsonify({"error": "Missing data for notification"}), 400

    user_id = data["user_id"]
    channel = data["channel"]
    content = data["content"]
    notification_type = data.get("notification_type", "generic")

    notification = Notification(user_id, channel, content, notification_type)

    if redis_client:
        try:
            redis_client.rpush("notification_queue", json.dumps(notification.to_dict()))
            logger.info(f"Notification added to queue for user {user_id} via {channel}")
            return jsonify({"message": "Notification queued successfully"}), 202
        except Exception as e:
            logger.error(f"Failed to add notification to Redis queue: {e}")
            return jsonify({"error": "Failed to queue notification", "details": str(e)}), 500
    else:
        logger.error("Redis client not available, cannot queue notification.")
        return jsonify({"error": "Notification service temporarily unavailable"}), 503

# هنا يمكن إضافة منطق لمعالجة قائمة الانتظار بشكل دوري (مثال)
# في بيئة إنتاج، قد تستخدم Celery Workers أو وظائف خلفية أخرى
def process_notification_queue():
    if redis_client:
        while True:
            # BPOP (blocking pop) للحصول على إشعار من قائمة الانتظار
            item = redis_client.blpop("notification_queue", timeout=1)
            if item:
                notification_data = json.loads(item[1])
                notification = Notification(**notification_data)
                logger.info(f"Processing notification for user {notification.user_id} via {notification.channel}")
                
                # محاكاة إرسال الإشعارات
                if notification.channel == "email":
                    logger.info(f"Sending email to {notification.user_id}: {notification.content}")
                    # هنا يتم استدعاء خدمة إرسال البريد الإلكتروني الفعلية
                elif notification.channel == "sms":
                    logger.info(f"Sending SMS to {notification.user_id}: {notification.content}")
                    # هنا يتم استدعاء خدمة إرسال الرسائل النصية الفعلية (مثل Twilio)
                elif notification.channel == "push":
                    logger.info(f"Sending push notification to {notification.user_id}: {notification.content}")
                    # هنا يتم استدعاء خدمة إرسال إشعارات الدفع (مثل FCM)
                else:
                    logger.warning(f"Unknown notification channel: {notification.channel}")

# يمكن تشغيل process_notification_queue في thread منفصل أو كـ background job
# if __name__ == "__main__":
#     import threading
#     notification_processor_thread = threading.Thread(target=process_notification_queue)
#     notification_processor_thread.daemon = True
#     notification_processor_thread.start()
#     app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)

