#!/usr/bin/env python3
"""
مثال عملي لاختبار نظام الإشعارات
"""

import requests
import json
import time

# إعدادات الخدمة
SERVICE_URL = "http://localhost:8003"

def test_notification_system():
    """اختبار شامل لنظام الإشعارات"""
    
    print("🧪 اختبار نظام الإشعارات - نائبك")
    print("=" * 50)
    
    # 1. فحص حالة الخدمة
    print("\n1️⃣ فحص حالة الخدمة...")
    try:
        response = requests.get(f"{SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ الخدمة تعمل بنجاح")
            print(f"📊 البيانات: {response.json()}")
        else:
            print("❌ الخدمة لا تعمل")
            return
    except:
        print("❌ لا يمكن الوصول للخدمة - تأكد من تشغيلها أولاً")
        print("💡 شغل الخدمة بالأمر: python notifications_clean.py")
        return
    
    # 2. فحص القنوات المتاحة
    print("\n2️⃣ فحص القنوات المتاحة...")
    response = requests.get(f"{SERVICE_URL}/channels")
    channels_data = response.json()
    print(f"📋 القنوات: {channels_data['channels']}")
    
    # 3. إرسال إشعار داخلي
    print("\n3️⃣ إرسال إشعار داخلي...")
    notification_data = {
        "user_id": "123",
        "title": "🔔 رسالة جديدة",
        "body": "لديك رسالة جديدة من النائب أحمد محمد حول استفسارك",
        "channels": ["in_app"],
        "data": {
            "type": "message",
            "from": "deputy_456",
            "message_id": "msg_001",
            "priority": "normal"
        }
    }
    
    response = requests.post(
        f"{SERVICE_URL}/send",
        json=notification_data,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        print("✅ تم إرسال الإشعار الداخلي بنجاح")
        print(f"📤 النتيجة: {response.json()}")
    else:
        print(f"❌ فشل إرسال الإشعار: {response.text}")
    
    # 4. إرسال إشعار بريد إلكتروني
    print("\n4️⃣ إرسال إشعار بريد إلكتروني...")
    email_notification = {
        "user_id": "123",
        "title": "📧 تحديث في شكواك",
        "body": "تم الرد على شكواك رقم #2024001. يرجى مراجعة التطبيق للاطلاع على التفاصيل.",
        "channels": ["email"],
        "data": {
            "type": "complaint_update",
            "complaint_id": "2024001",
            "status": "replied"
        }
    }
    
    response = requests.post(
        f"{SERVICE_URL}/send",
        json=email_notification,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        print("✅ تم إرسال إشعار البريد الإلكتروني بنجاح")
        print(f"📧 النتيجة: {response.json()}")
    else:
        print(f"❌ فشل إرسال البريد الإلكتروني: {response.text}")
    
    # 5. إرسال إشعارات متعددة
    print("\n5️⃣ إرسال إشعارات متعددة...")
    multi_notification = {
        "user_id": "123",
        "title": "🚨 إشعار عاجل",
        "body": "اجتماع عام مع النائب غداً الساعة 7 مساءً في قاعة المؤتمرات",
        "channels": ["in_app", "email"],
        "data": {
            "type": "public_meeting",
            "date": "2024-09-27",
            "time": "19:00",
            "location": "قاعة المؤتمرات",
            "priority": "urgent"
        }
    }
    
    response = requests.post(
        f"{SERVICE_URL}/send",
        json=multi_notification,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        print("✅ تم إرسال الإشعارات المتعددة بنجاح")
        print(f"📨 النتيجة: {response.json()}")
    else:
        print(f"❌ فشل إرسال الإشعارات المتعددة: {response.text}")
    
    # 6. جلب إشعارات المستخدم
    print("\n6️⃣ جلب إشعارات المستخدم...")
    response = requests.get(f"{SERVICE_URL}/notifications/123")
    
    if response.status_code == 200:
        notifications = response.json()
        print(f"✅ تم جلب الإشعارات بنجاح")
        print(f"📱 عدد الإشعارات: {notifications['count']}")
        
        if notifications['notifications']:
            print("\n📋 آخر الإشعارات:")
            for i, notif in enumerate(notifications['notifications'][:3]):
                print(f"   {i+1}. {notif['title']}")
                print(f"      📝 {notif['body']}")
                print(f"      🕐 {notif['timestamp']}")
                print(f"      👁️ مقروء: {'نعم' if notif['read'] else 'لا'}")
                print()
    else:
        print(f"❌ فشل جلب الإشعارات: {response.text}")
    
    print("\n" + "=" * 50)
    print("🎉 انتهى الاختبار!")
    print("\n💡 ملاحظات:")
    print("   - الإشعارات الداخلية تُحفظ في Redis")
    print("   - البريد الإلكتروني يُسجل في اللوج (للاختبار)")
    print("   - يمكن ربط الجرس بالواجهة الأمامية")
    print("   - النظام جاهز للاستخدام الفوري!")

if __name__ == "__main__":
    test_notification_system()
