# 🏷️ خدمة الإشعارات (naebak-notifications-service)

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/egyptofrance/naebak-notifications-service/actions)
[![Coverage](https://img.shields.io/badge/coverage-N/A-lightgrey)](https://github.com/egyptofrance/naebak-notifications-service)
[![Version](https://img.shields.io/badge/version-0.2.0-blue)](https://github.com/egyptofrance/naebak-notifications-service/releases)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

## 🚨 تحديث مهم - سبتمبر 2024

**تم إزالة ميزات SMS والإشعارات الفورية (Push Notifications) من الخدمة**

### السبب:
- هذه الميزات **غير مطلوبة حالياً** في المشروع
- تسبب تعقيدات في التشغيل والصيانة  
- تعتمد على خدمات خارجية مدفوعة (Twilio, Firebase)
- تزيد من تكلفة التشغيل بدون فائدة حقيقية

## 📝 الوصف

خدمة إرسال الإشعارات للمستخدمين. تدعم إرسال الإشعارات عبر البريد الإلكتروني والإشعارات الداخلية و Webhooks.

---

## ✅ الميزات المتاحة

### القنوات المدعومة:
- **📧 البريد الإلكتروني** - إرسال عبر SMTP
- **📱 الإشعارات الداخلية** - تخزين في Redis للعرض داخل التطبيق  
- **🔗 Webhooks** - إرسال إشعارات عبر HTTP POST

### ❌ الميزات المحذوفة:
- **📱 رسائل SMS** - محذوفة (كانت تتطلب Twilio)
- **🔔 الإشعارات الفورية** - محذوفة (كانت تتطلب Firebase)

---

## 🛠️ التقنيات المستخدمة

| التقنية | الإصدار | الغرض |
|---------|---------|-------|
| **Flask** | 2.3.2 | إطار العمل الأساسي |
| **Celery** | 5.3+ | جدولة المهام |

---

## 🚀 التثبيت والتشغيل

```bash
git clone https://github.com/egyptofrance/naebak-notifications-service.git
cd naebak-notifications-service

# اتبع خطوات التثبيت والتشغيل لخدمات Flask
```

---

## 📚 توثيق الـ API

- **Swagger UI**: [http://localhost:5003/api/docs/](http://localhost:5003/api/docs/)

---

## 🤝 المساهمة

يرجى مراجعة [دليل المساهمة](CONTRIBUTING.md) و [معايير التوثيق الموحدة](../../naebak-almakhzan/DOCUMENTATION_STANDARDS.md).

---

## 📄 الترخيص

هذا المشروع مرخص تحت [رخصة MIT](LICENSE).

