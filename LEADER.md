# 🔔 LEADER - دليل خدمة الإشعارات (Notifications Service)

**اسم الخدمة:** naebak-notifications-service  
**المنفذ:** 8008  
**الإطار:** Flask 2.3  
**قاعدة البيانات:** Redis (لإدارة قائمة الانتظار)  
**النوع:** Notification Management (إدارة الإشعارات)  

---

## 📋 **نظرة عامة على الخدمة**

### **🎯 الغرض الأساسي:**
خدمة الإشعارات هي المسؤولة عن إرسال جميع أنواع الإشعارات للمستخدمين، سواء كانت إشعارات عبر البريد الإلكتروني، رسائل نصية (SMS)، أو إشعارات لحظية (Push Notifications) على تطبيقات الجوال.

### **📝 كيف يعمل التطبيق بالضبط:**

**للمطور - فهم إرسال الإشعارات:**
1. **قائمة انتظار (Queue):** عند الحاجة لإرسال إشعار، يتم إضافته إلى قائمة انتظار في Redis.
2. **معالجة الإشعارات:** تقوم الخدمة بمعالجة الإشعارات من قائمة الانتظار بشكل دوري.
3. **إرسال عبر قنوات مختلفة:** تدعم الخدمة إرسال الإشعارات عبر قنوات متعددة (Email, SMS, Push).

**مثال عملي:**
```
مستخدم جديد يسجل في المنصة
↓
خدمة المصادقة (Auth Service) ترسل طلبًا إلى خدمة الإشعارات لإرسال بريد ترحيبي
↓
خدمة الإشعارات تضيف الإشعار إلى قائمة الانتظار في Redis
↓
تقوم الخدمة بمعالجة الإشعار وإرسال بريد إلكتروني للمستخدم الجديد
```

---

## 🌐 **دور الخدمة في منصة نائبك**

### **🏛️ المكانة في النظام:**
خدمة الإشعارات هي **حلقة الوصل** بين المنصة والمستخدمين، حيث تبقيهم على اطلاع دائم بآخر المستجدات.

### **📡 العلاقات مع الخدمات الأخرى:**

#### **🔗 الخدمات المرتبطة:**
- **خدمة البوابة (Gateway):** توجه الطلبات إلى خدمة الإشعارات.
- **جميع الخدمات الأخرى:** يمكن لأي خدمة أخرى طلب إرسال إشعار.

---

## 📊 **البيانات الأساسية**

### **📝 نماذج البيانات:**
```python
# نموذج لإشعار
class Notification:
    def __init__(self, user_id, channel, content):
        self.user_id = user_id
        self.channel = channel  # email, sms, push
        self.content = content
        self.timestamp = datetime.utcnow()
```

---

## ⚙️ **إعدادات Google Cloud Run**

### **🔧 بيئة التطوير:**
```yaml
Environment: development
Port: 8008
Resources:
  CPU: 0.2
  Memory: 128Mi
  Max Instances: 1

Environment Variables:
  FLASK_ENV=development
  REDIS_URL=redis://localhost:6379
  DEBUG=true
```

### **🚀 بيئة الإنتاج:**
```yaml
Environment: production
Port: 8008
Resources:
  CPU: 0.3
  Memory: 256Mi
  Max Instances: 5
  Min Instances: 1

Environment Variables:
  FLASK_ENV=production
  REDIS_URL=${REDIS_URL_FROM_SECRET_MANAGER}
  DEBUG=false
```

