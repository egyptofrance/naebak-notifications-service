# Naebak Notifications Service - API Documentation

## Overview

The Naebak Notifications Service provides comprehensive multi-channel notification capabilities for the Naebak platform. It supports email, SMS, push notifications, and in-app notifications with advanced features like templating, user preferences, scheduling, and delivery tracking.

## Base URL

```
http://localhost:8008
```

## Authentication

All API endpoints (except health check and webhooks) require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

## API Endpoints

### Health Check

#### GET /health

Check service health and status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "celery": "active"
  }
}
```

### Notifications

#### POST /notifications

Create a new notification.

**Request Body:**
```json
{
  "user_id": "user-uuid",
  "notification_type": "welcome",
  "channel": "email",
  "content": "Welcome to Naebak platform!",
  "subject": "Welcome!",
  "priority": "normal",
  "scheduled_at": "2024-01-15T15:30:00Z",
  "variables": {
    "user_name": "أحمد محمد",
    "platform_name": "نائبك"
  }
}
```

**Parameters:**
- `user_id` (string, required): Target user ID
- `notification_type` (string, required): Type of notification
  - Values: `welcome`, `password_reset`, `new_message`, `complaint_update`, `election_alert`, `system_maintenance`, `reminder`, `announcement`
- `channel` (string, required): Delivery channel
  - Values: `email`, `sms`, `push`, `in_app`
- `content` (string, required): Notification content
- `subject` (string, optional): Notification subject (for email)
- `priority` (string, optional): Notification priority
  - Values: `low`, `normal`, `high`, `urgent`
  - Default: `normal`
- `scheduled_at` (string, optional): ISO datetime for scheduled delivery
- `variables` (object, optional): Template variables for content rendering

**Response:**
```json
{
  "id": "notification-uuid",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z",
  "scheduled_at": "2024-01-15T15:30:00Z"
}
```

#### GET /notifications/{notification_id}

Get notification details by ID.

**Response:**
```json
{
  "id": "notification-uuid",
  "user_id": "user-uuid",
  "notification_type": "welcome",
  "channel": "email",
  "content": "Welcome to Naebak platform!",
  "subject": "Welcome!",
  "priority": "normal",
  "status": "delivered",
  "created_at": "2024-01-15T10:30:00Z",
  "scheduled_at": null,
  "sent_at": "2024-01-15T10:31:00Z",
  "delivered_at": "2024-01-15T10:31:30Z",
  "error_message": null,
  "retry_count": 0,
  "variables": {
    "user_name": "أحمد محمد"
  }
}
```

#### GET /notifications

List notifications with filtering and pagination.

**Query Parameters:**
- `user_id` (string, optional): Filter by user ID
- `notification_type` (string, optional): Filter by notification type
- `channel` (string, optional): Filter by channel
- `status` (string, optional): Filter by status
  - Values: `pending`, `sent`, `delivered`, `failed`, `cancelled`
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page (default: 20, max: 100)

**Response:**
```json
{
  "notifications": [
    {
      "id": "notification-uuid",
      "user_id": "user-uuid",
      "notification_type": "welcome",
      "channel": "email",
      "content": "Welcome to Naebak platform!",
      "subject": "Welcome!",
      "priority": "normal",
      "status": "delivered",
      "created_at": "2024-01-15T10:30:00Z",
      "sent_at": "2024-01-15T10:31:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "pages": 8
  }
}
```

#### POST /notifications/{notification_id}/retry

Retry a failed notification.

**Response:**
```json
{
  "message": "Notification queued for retry",
  "status": "pending"
}
```

### User Preferences

#### GET /users/{user_id}/preferences

Get notification preferences for a user.

**Response:**
```json
{
  "user_id": "user-uuid",
  "preferences": {
    "welcome": {
      "email": {
        "enabled": true,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00"
      },
      "sms": {
        "enabled": false
      },
      "push": {
        "enabled": true,
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "07:00"
      },
      "in_app": {
        "enabled": true
      }
    },
    "new_message": {
      "email": {
        "enabled": true
      },
      "push": {
        "enabled": true
      }
    }
  }
}
```

#### PUT /users/{user_id}/preferences

Update notification preferences for a user.

**Request Body:**
```json
{
  "preferences": {
    "welcome": {
      "email": {
        "enabled": true,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00"
      },
      "sms": {
        "enabled": false
      }
    }
  }
}
```

**Response:**
```json
{
  "message": "Updated 2 preferences",
  "user_id": "user-uuid"
}
```

### Templates (Admin Only)

#### GET /templates

List notification templates.

**Query Parameters:**
- `notification_type` (string, optional): Filter by notification type
- `channel` (string, optional): Filter by channel
- `active_only` (boolean, optional): Show only active templates

**Response:**
```json
{
  "templates": [
    {
      "id": "template-uuid",
      "name": "Welcome Email Template",
      "notification_type": "welcome",
      "channel": "email",
      "subject": "Welcome to {{platform_name}}!",
      "content": "Hello {{user_name}}, welcome to our platform!",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "created_by": "admin-user-id"
    }
  ]
}
```

#### POST /templates

Create a new notification template.

**Request Body:**
```json
{
  "name": "Welcome Email Template",
  "notification_type": "welcome",
  "channel": "email",
  "content": "Hello {{user_name}}, welcome to {{platform_name}}!",
  "subject": "Welcome to {{platform_name}}!",
  "variables": {
    "user_name": "string",
    "platform_name": "string"
  }
}
```

**Response:**
```json
{
  "id": "template-uuid",
  "name": "Welcome Email Template",
  "notification_type": "welcome",
  "channel": "email",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Bulk Operations (Admin Only)

#### POST /bulk/send

Send bulk notifications to multiple users.

**Request Body:**
```json
{
  "user_ids": ["user-1", "user-2", "user-3"],
  "notification_type": "announcement",
  "channel": "email",
  "content": "Important announcement for all users",
  "subject": "Important Announcement",
  "priority": "high",
  "variables": {
    "announcement_title": "Platform Update"
  }
}
```

**Response:**
```json
{
  "message": "Queued 3 notifications for delivery",
  "notification_ids": [
    "notification-1-uuid",
    "notification-2-uuid",
    "notification-3-uuid"
  ]
}
```

### Statistics (Admin Only)

#### GET /stats

Get notification statistics.

**Query Parameters:**
- `days` (integer, optional): Number of days to include (default: 7)
- `user_id` (string, optional): Filter by user ID

**Response:**
```json
{
  "period": {
    "start_date": "2024-01-08T10:30:00Z",
    "end_date": "2024-01-15T10:30:00Z",
    "days": 7
  },
  "total_notifications": 1250,
  "by_status": {
    "pending": 15,
    "sent": 50,
    "delivered": 1150,
    "failed": 25,
    "cancelled": 10
  },
  "by_channel": {
    "email": 800,
    "sms": 200,
    "push": 200,
    "in_app": 50
  },
  "by_type": {
    "welcome": 100,
    "new_message": 500,
    "complaint_update": 300,
    "election_alert": 200,
    "system_maintenance": 50,
    "reminder": 100
  }
}
```

### Webhooks

#### POST /webhooks/sendgrid

Handle SendGrid delivery status webhooks.

**Request Body:**
```json
[
  {
    "event": "delivered",
    "email": "user@example.com",
    "timestamp": 1642248600,
    "sg_message_id": "sendgrid-message-id"
  }
]
```

#### POST /webhooks/twilio

Handle Twilio delivery status webhooks.

**Request Body:**
```
MessageStatus=delivered&MessageSid=twilio-message-sid&To=%2B1987654321&From=%2B1234567890
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error description",
  "details": "Additional error details (optional)"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `202` - Accepted (for async operations)
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error
- `503` - Service Unavailable

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Development**: 120 requests/minute, 2000 requests/hour
- **Production**: 30 requests/minute, 500 requests/hour

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets

## Notification Types

### Available Types

1. **welcome** - User registration and onboarding
2. **password_reset** - Security-related notifications
3. **new_message** - Communication alerts
4. **complaint_update** - Status updates for complaints
5. **election_alert** - Political events and elections
6. **system_maintenance** - Platform maintenance notices
7. **reminder** - General reminders
8. **announcement** - Platform announcements

### Delivery Channels

1. **email** - HTML/text email notifications
2. **sms** - Short text message notifications
3. **push** - Mobile and web push notifications
4. **in_app** - Real-time in-application notifications

### Priority Levels

1. **low** - Non-urgent notifications (delivered during business hours)
2. **normal** - Standard notifications (default)
3. **high** - Important notifications (bypass quiet hours)
4. **urgent** - Critical notifications (immediate delivery)

## Template Variables

Templates support Jinja2-style variable substitution:

### Common Variables
- `{{user_name}}` - User's display name
- `{{platform_name}}` - Platform name (نائبك)
- `{{current_date}}` - Current date
- `{{current_time}}` - Current time

### Context-Specific Variables
- `{{complaint_id}}` - For complaint updates
- `{{message_sender}}` - For new message notifications
- `{{election_date}}` - For election alerts
- `{{maintenance_start}}` - For maintenance notifications

## User Preferences

Users can configure notification preferences for each combination of notification type and delivery channel:

### Preference Options
- `enabled` (boolean) - Whether to receive notifications
- `quiet_hours_start` (string) - Start of quiet hours (HH:MM format)
- `quiet_hours_end` (string) - End of quiet hours (HH:MM format)
- `frequency` (string) - Delivery frequency (immediate, hourly, daily)

### Default Preferences
- All notification types are enabled by default
- Quiet hours: 22:00 - 08:00 for email and push
- SMS notifications respect quiet hours for non-urgent messages
- In-app notifications are not affected by quiet hours

## Integration Examples

### JavaScript (Frontend)

```javascript
// Create a notification
const response = await fetch('/notifications', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    user_id: 'user-123',
    notification_type: 'welcome',
    channel: 'email',
    content: 'Welcome to Naebak!',
    subject: 'Welcome!'
  })
});

const notification = await response.json();
console.log('Notification created:', notification.id);
```

### Python (Backend Service)

```python
import requests

def send_notification(user_id, message):
    response = requests.post(
        'http://notifications-service:8008/notifications',
        headers={
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        },
        json={
            'user_id': user_id,
            'notification_type': 'new_message',
            'channel': 'push',
            'content': message
        }
    )
    return response.json()
```

### cURL

```bash
# Create a notification
curl -X POST http://localhost:8008/notifications \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "notification_type": "welcome",
    "channel": "email",
    "content": "Welcome to Naebak platform!",
    "subject": "Welcome!"
  }'
```

## Best Practices

### 1. Error Handling
Always check response status codes and handle errors appropriately:

```javascript
if (response.status === 429) {
  // Rate limit exceeded, implement backoff
  await new Promise(resolve => setTimeout(resolve, 60000));
  // Retry request
}
```

### 2. Bulk Operations
Use bulk endpoints for sending notifications to multiple users:

```javascript
// Instead of multiple individual requests
for (const userId of userIds) {
  await sendNotification(userId, message); // Don't do this
}

// Use bulk endpoint
await sendBulkNotifications(userIds, message); // Do this
```

### 3. Template Usage
Use templates for consistent messaging:

```javascript
// Create reusable templates for common notifications
const welcomeTemplate = {
  name: 'User Welcome Email',
  notification_type: 'welcome',
  channel: 'email',
  subject: 'Welcome to {{platform_name}}!',
  content: 'Hello {{user_name}}, welcome to our platform!'
};
```

### 4. User Preferences
Respect user preferences and quiet hours:

```javascript
// Check user preferences before sending
const preferences = await getUserPreferences(userId);
if (!preferences.new_message.email.enabled) {
  // Use alternative channel or skip
}
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check JWT token validity
   - Ensure token is included in Authorization header

2. **403 Forbidden**
   - Verify user has required permissions
   - Admin-only endpoints require admin role

3. **429 Rate Limited**
   - Implement exponential backoff
   - Consider using bulk endpoints

4. **500 Internal Server Error**
   - Check service logs
   - Verify external service configurations (SendGrid, Twilio, etc.)

### Monitoring

Monitor these metrics for service health:
- Notification delivery rates by channel
- Failed notification counts and reasons
- API response times and error rates
- Queue lengths and processing times

For support, contact the development team or check the service logs for detailed error information.
