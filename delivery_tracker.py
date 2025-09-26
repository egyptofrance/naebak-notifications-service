#!/usr/bin/env python3
"""
Naebak Notifications Service - Delivery Tracker
===============================================

Advanced delivery tracking system for monitoring notification delivery
status across multiple channels with real-time updates and analytics.

Features:
- Real-time delivery status tracking
- Retry mechanism with exponential backoff
- Delivery analytics and reporting
- Webhook callbacks for status updates
- Batch status updates
- Performance monitoring
- Error categorization and analysis
"""

import time
import json
import uuid
import redis
import logging
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
from threading import Thread, Lock
import requests
from typing import Dict, List, Optional, Tuple
import asyncio
import aiohttp
from dataclasses import dataclass, asdict
from config import Config

logger = logging.getLogger(__name__)

class DeliveryStatus(Enum):
    """Delivery status enumeration"""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class DeliveryChannel(Enum):
    """Delivery channel enumeration"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"

class FailureReason(Enum):
    """Failure reason categorization"""
    INVALID_RECIPIENT = "invalid_recipient"
    NETWORK_ERROR = "network_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    CONTENT_REJECTED = "content_rejected"
    RECIPIENT_BLOCKED = "recipient_blocked"
    QUOTA_EXCEEDED = "quota_exceeded"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

@dataclass
class DeliveryAttempt:
    """Represents a delivery attempt"""
    attempt_id: str
    timestamp: datetime
    status: DeliveryStatus
    error_message: Optional[str] = None
    response_code: Optional[int] = None
    response_data: Optional[Dict] = None
    duration_ms: Optional[int] = None

@dataclass
class DeliveryRecord:
    """Represents a complete delivery record"""
    delivery_id: str
    notification_id: str
    user_id: str
    channel: DeliveryChannel
    recipient: str
    status: DeliveryStatus
    created_at: datetime
    updated_at: datetime
    attempts: List[DeliveryAttempt]
    metadata: Dict
    webhook_url: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    failure_reason: Optional[FailureReason] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

class DeliveryTracker:
    """Main delivery tracking system"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB
        )
        self.delivery_records: Dict[str, DeliveryRecord] = {}
        self.status_callbacks: Dict[str, List[callable]] = defaultdict(list)
        self.webhook_queue = deque()
        self.analytics = DeliveryAnalytics()
        self.lock = Lock()
        
        # Start background workers
        self._start_background_workers()
    
    def create_delivery_record(self, notification_id: str, user_id: str, 
                             channel: DeliveryChannel, recipient: str,
                             metadata: Dict = None, webhook_url: str = None) -> str:
        """Create a new delivery record"""
        delivery_id = str(uuid.uuid4())
        
        record = DeliveryRecord(
            delivery_id=delivery_id,
            notification_id=notification_id,
            user_id=user_id,
            channel=channel,
            recipient=recipient,
            status=DeliveryStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            attempts=[],
            metadata=metadata or {},
            webhook_url=webhook_url
        )
        
        with self.lock:
            self.delivery_records[delivery_id] = record
        
        # Store in Redis for persistence
        self._store_record_in_redis(record)
        
        logger.info(f"Created delivery record {delivery_id} for notification {notification_id}")
        return delivery_id
    
    def update_delivery_status(self, delivery_id: str, status: DeliveryStatus,
                             error_message: str = None, response_code: int = None,
                             response_data: Dict = None, duration_ms: int = None) -> bool:
        """Update delivery status"""
        try:
            with self.lock:
                record = self.delivery_records.get(delivery_id)
                if not record:
                    # Try to load from Redis
                    record = self._load_record_from_redis(delivery_id)
                    if not record:
                        logger.error(f"Delivery record {delivery_id} not found")
                        return False
                
                # Create attempt record
                attempt = DeliveryAttempt(
                    attempt_id=str(uuid.uuid4()),
                    timestamp=datetime.utcnow(),
                    status=status,
                    error_message=error_message,
                    response_code=response_code,
                    response_data=response_data,
                    duration_ms=duration_ms
                )
                
                # Update record
                record.attempts.append(attempt)
                record.status = status
                record.updated_at = datetime.utcnow()
                
                # Set specific timestamps
                if status == DeliveryStatus.DELIVERED:
                    record.delivered_at = datetime.utcnow()
                elif status == DeliveryStatus.READ:
                    record.read_at = datetime.utcnow()
                elif status in [DeliveryStatus.FAILED, DeliveryStatus.BOUNCED, DeliveryStatus.REJECTED]:
                    record.failure_reason = self._categorize_failure(error_message, response_code)
                    
                    # Schedule retry if applicable
                    if record.retry_count < record.max_retries and self._should_retry(record.failure_reason):
                        record.retry_count += 1
                        record.next_retry_at = self._calculate_next_retry(record.retry_count)
                        record.status = DeliveryStatus.QUEUED
                        logger.info(f"Scheduled retry {record.retry_count} for delivery {delivery_id}")
                
                self.delivery_records[delivery_id] = record
            
            # Store updated record in Redis
            self._store_record_in_redis(record)
            
            # Trigger callbacks
            self._trigger_status_callbacks(delivery_id, status)
            
            # Queue webhook notification
            if record.webhook_url:
                self._queue_webhook_notification(record)
            
            # Update analytics
            self.analytics.record_delivery_event(record, attempt)
            
            logger.info(f"Updated delivery {delivery_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update delivery status for {delivery_id}: {str(e)}")
            return False
    
    def get_delivery_status(self, delivery_id: str) -> Optional[DeliveryRecord]:
        """Get delivery record by ID"""
        with self.lock:
            record = self.delivery_records.get(delivery_id)
            if not record:
                record = self._load_record_from_redis(delivery_id)
            return record
    
    def get_delivery_history(self, notification_id: str) -> List[DeliveryRecord]:
        """Get all delivery records for a notification"""
        records = []
        
        # Search in memory
        with self.lock:
            for record in self.delivery_records.values():
                if record.notification_id == notification_id:
                    records.append(record)
        
        # Search in Redis if needed
        redis_records = self._search_records_in_redis('notification_id', notification_id)
        for record in redis_records:
            if record.delivery_id not in [r.delivery_id for r in records]:
                records.append(record)
        
        return sorted(records, key=lambda x: x.created_at)
    
    def get_user_deliveries(self, user_id: str, channel: DeliveryChannel = None,
                           status: DeliveryStatus = None, limit: int = 100) -> List[DeliveryRecord]:
        """Get delivery records for a user"""
        records = []
        
        # Search in memory
        with self.lock:
            for record in self.delivery_records.values():
                if record.user_id == user_id:
                    if channel and record.channel != channel:
                        continue
                    if status and record.status != status:
                        continue
                    records.append(record)
        
        # Search in Redis if needed
        redis_records = self._search_records_in_redis('user_id', user_id)
        for record in redis_records:
            if record.delivery_id not in [r.delivery_id for r in records]:
                if channel and record.channel != channel:
                    continue
                if status and record.status != status:
                    continue
                records.append(record)
        
        # Sort and limit
        records = sorted(records, key=lambda x: x.created_at, reverse=True)
        return records[:limit]
    
    def register_status_callback(self, delivery_id: str, callback: callable):
        """Register callback for status updates"""
        self.status_callbacks[delivery_id].append(callback)
    
    def get_delivery_analytics(self, start_date: datetime = None, 
                             end_date: datetime = None) -> Dict:
        """Get delivery analytics"""
        return self.analytics.get_analytics(start_date, end_date)
    
    def get_channel_performance(self, channel: DeliveryChannel,
                               start_date: datetime = None,
                               end_date: datetime = None) -> Dict:
        """Get performance metrics for a specific channel"""
        return self.analytics.get_channel_performance(channel, start_date, end_date)
    
    def get_retry_queue(self) -> List[DeliveryRecord]:
        """Get records that need to be retried"""
        now = datetime.utcnow()
        retry_records = []
        
        with self.lock:
            for record in self.delivery_records.values():
                if (record.status == DeliveryStatus.QUEUED and 
                    record.next_retry_at and 
                    record.next_retry_at <= now):
                    retry_records.append(record)
        
        return retry_records
    
    def mark_for_retry(self, delivery_id: str, delay_seconds: int = None) -> bool:
        """Mark a delivery for retry"""
        try:
            with self.lock:
                record = self.delivery_records.get(delivery_id)
                if not record:
                    return False
                
                if record.retry_count >= record.max_retries:
                    logger.warning(f"Delivery {delivery_id} has exceeded max retries")
                    return False
                
                record.retry_count += 1
                record.status = DeliveryStatus.QUEUED
                
                if delay_seconds:
                    record.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
                else:
                    record.next_retry_at = self._calculate_next_retry(record.retry_count)
                
                record.updated_at = datetime.utcnow()
            
            self._store_record_in_redis(record)
            logger.info(f"Marked delivery {delivery_id} for retry")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark delivery {delivery_id} for retry: {str(e)}")
            return False
    
    def cancel_delivery(self, delivery_id: str, reason: str = None) -> bool:
        """Cancel a pending delivery"""
        try:
            with self.lock:
                record = self.delivery_records.get(delivery_id)
                if not record:
                    return False
                
                if record.status in [DeliveryStatus.DELIVERED, DeliveryStatus.READ]:
                    logger.warning(f"Cannot cancel already delivered notification {delivery_id}")
                    return False
                
                record.status = DeliveryStatus.CANCELLED
                record.updated_at = datetime.utcnow()
                
                if reason:
                    record.metadata['cancellation_reason'] = reason
            
            self._store_record_in_redis(record)
            self._trigger_status_callbacks(delivery_id, DeliveryStatus.CANCELLED)
            
            logger.info(f"Cancelled delivery {delivery_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel delivery {delivery_id}: {str(e)}")
            return False
    
    def _store_record_in_redis(self, record: DeliveryRecord):
        """Store delivery record in Redis"""
        try:
            key = f"delivery:{record.delivery_id}"
            data = {
                'delivery_id': record.delivery_id,
                'notification_id': record.notification_id,
                'user_id': record.user_id,
                'channel': record.channel.value,
                'recipient': record.recipient,
                'status': record.status.value,
                'created_at': record.created_at.isoformat(),
                'updated_at': record.updated_at.isoformat(),
                'attempts': [asdict(attempt) for attempt in record.attempts],
                'metadata': record.metadata,
                'webhook_url': record.webhook_url,
                'retry_count': record.retry_count,
                'max_retries': record.max_retries,
                'next_retry_at': record.next_retry_at.isoformat() if record.next_retry_at else None,
                'failure_reason': record.failure_reason.value if record.failure_reason else None,
                'delivered_at': record.delivered_at.isoformat() if record.delivered_at else None,
                'read_at': record.read_at.isoformat() if record.read_at else None
            }
            
            self.redis_client.setex(key, 86400 * 7, json.dumps(data))  # 7 days TTL
            
            # Add to indexes
            self.redis_client.sadd(f"deliveries:notification:{record.notification_id}", record.delivery_id)
            self.redis_client.sadd(f"deliveries:user:{record.user_id}", record.delivery_id)
            self.redis_client.sadd(f"deliveries:channel:{record.channel.value}", record.delivery_id)
            
        except Exception as e:
            logger.error(f"Failed to store record in Redis: {str(e)}")
    
    def _load_record_from_redis(self, delivery_id: str) -> Optional[DeliveryRecord]:
        """Load delivery record from Redis"""
        try:
            key = f"delivery:{delivery_id}"
            data = self.redis_client.get(key)
            
            if not data:
                return None
            
            data = json.loads(data)
            
            # Convert back to objects
            attempts = []
            for attempt_data in data.get('attempts', []):
                attempt = DeliveryAttempt(
                    attempt_id=attempt_data['attempt_id'],
                    timestamp=datetime.fromisoformat(attempt_data['timestamp']),
                    status=DeliveryStatus(attempt_data['status']),
                    error_message=attempt_data.get('error_message'),
                    response_code=attempt_data.get('response_code'),
                    response_data=attempt_data.get('response_data'),
                    duration_ms=attempt_data.get('duration_ms')
                )
                attempts.append(attempt)
            
            record = DeliveryRecord(
                delivery_id=data['delivery_id'],
                notification_id=data['notification_id'],
                user_id=data['user_id'],
                channel=DeliveryChannel(data['channel']),
                recipient=data['recipient'],
                status=DeliveryStatus(data['status']),
                created_at=datetime.fromisoformat(data['created_at']),
                updated_at=datetime.fromisoformat(data['updated_at']),
                attempts=attempts,
                metadata=data.get('metadata', {}),
                webhook_url=data.get('webhook_url'),
                retry_count=data.get('retry_count', 0),
                max_retries=data.get('max_retries', 3),
                next_retry_at=datetime.fromisoformat(data['next_retry_at']) if data.get('next_retry_at') else None,
                failure_reason=FailureReason(data['failure_reason']) if data.get('failure_reason') else None,
                delivered_at=datetime.fromisoformat(data['delivered_at']) if data.get('delivered_at') else None,
                read_at=datetime.fromisoformat(data['read_at']) if data.get('read_at') else None
            )
            
            return record
            
        except Exception as e:
            logger.error(f"Failed to load record from Redis: {str(e)}")
            return None
    
    def _search_records_in_redis(self, field: str, value: str) -> List[DeliveryRecord]:
        """Search records in Redis by field"""
        try:
            index_key = f"deliveries:{field}:{value}"
            delivery_ids = self.redis_client.smembers(index_key)
            
            records = []
            for delivery_id in delivery_ids:
                record = self._load_record_from_redis(delivery_id.decode())
                if record:
                    records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"Failed to search records in Redis: {str(e)}")
            return []
    
    def _categorize_failure(self, error_message: str, response_code: int) -> FailureReason:
        """Categorize failure reason"""
        if not error_message and not response_code:
            return FailureReason.UNKNOWN
        
        error_message = (error_message or "").lower()
        
        # Network errors
        if any(term in error_message for term in ['timeout', 'connection', 'network']):
            return FailureReason.NETWORK_ERROR
        
        # Authentication errors
        if any(term in error_message for term in ['auth', 'unauthorized', 'forbidden']):
            return FailureReason.AUTHENTICATION_FAILED
        
        # Rate limiting
        if any(term in error_message for term in ['rate limit', 'throttle', 'quota']):
            return FailureReason.RATE_LIMITED
        
        # Invalid recipient
        if any(term in error_message for term in ['invalid', 'not found', 'does not exist']):
            return FailureReason.INVALID_RECIPIENT
        
        # Content issues
        if any(term in error_message for term in ['spam', 'blocked', 'rejected']):
            return FailureReason.CONTENT_REJECTED
        
        # HTTP status codes
        if response_code:
            if response_code == 401:
                return FailureReason.AUTHENTICATION_FAILED
            elif response_code == 403:
                return FailureReason.RECIPIENT_BLOCKED
            elif response_code == 404:
                return FailureReason.INVALID_RECIPIENT
            elif response_code == 429:
                return FailureReason.RATE_LIMITED
            elif response_code >= 500:
                return FailureReason.SERVICE_UNAVAILABLE
        
        return FailureReason.UNKNOWN
    
    def _should_retry(self, failure_reason: FailureReason) -> bool:
        """Determine if delivery should be retried"""
        non_retryable_reasons = [
            FailureReason.INVALID_RECIPIENT,
            FailureReason.RECIPIENT_BLOCKED,
            FailureReason.CONTENT_REJECTED,
            FailureReason.AUTHENTICATION_FAILED
        ]
        
        return failure_reason not in non_retryable_reasons
    
    def _calculate_next_retry(self, retry_count: int) -> datetime:
        """Calculate next retry time with exponential backoff"""
        # Exponential backoff: 1min, 5min, 15min, 30min, 1hr
        delays = [60, 300, 900, 1800, 3600]
        delay_index = min(retry_count - 1, len(delays) - 1)
        delay_seconds = delays[delay_index]
        
        return datetime.utcnow() + timedelta(seconds=delay_seconds)
    
    def _trigger_status_callbacks(self, delivery_id: str, status: DeliveryStatus):
        """Trigger registered callbacks for status updates"""
        callbacks = self.status_callbacks.get(delivery_id, [])
        for callback in callbacks:
            try:
                callback(delivery_id, status)
            except Exception as e:
                logger.error(f"Callback error for delivery {delivery_id}: {str(e)}")
    
    def _queue_webhook_notification(self, record: DeliveryRecord):
        """Queue webhook notification for delivery status"""
        webhook_data = {
            'delivery_id': record.delivery_id,
            'notification_id': record.notification_id,
            'user_id': record.user_id,
            'channel': record.channel.value,
            'status': record.status.value,
            'timestamp': record.updated_at.isoformat(),
            'webhook_url': record.webhook_url
        }
        
        self.webhook_queue.append(webhook_data)
    
    def _start_background_workers(self):
        """Start background worker threads"""
        
        def webhook_worker():
            """Process webhook notifications"""
            while True:
                try:
                    if self.webhook_queue:
                        webhook_data = self.webhook_queue.popleft()
                        self._send_webhook_notification(webhook_data)
                    else:
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Webhook worker error: {str(e)}")
                    time.sleep(5)
        
        def cleanup_worker():
            """Clean up old records"""
            while True:
                try:
                    self._cleanup_old_records()
                    time.sleep(3600)  # Run every hour
                except Exception as e:
                    logger.error(f"Cleanup worker error: {str(e)}")
                    time.sleep(3600)
        
        # Start worker threads
        webhook_thread = Thread(target=webhook_worker, daemon=True)
        webhook_thread.start()
        
        cleanup_thread = Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def _send_webhook_notification(self, webhook_data: Dict):
        """Send webhook notification"""
        try:
            webhook_url = webhook_data.pop('webhook_url')
            
            response = requests.post(
                webhook_url,
                json=webhook_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook sent successfully for delivery {webhook_data['delivery_id']}")
            else:
                logger.warning(f"Webhook failed with status {response.status_code} for delivery {webhook_data['delivery_id']}")
                
        except Exception as e:
            logger.error(f"Failed to send webhook for delivery {webhook_data['delivery_id']}: {str(e)}")
    
    def _cleanup_old_records(self):
        """Clean up old delivery records"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            with self.lock:
                expired_ids = []
                for delivery_id, record in self.delivery_records.items():
                    if record.created_at < cutoff_date:
                        expired_ids.append(delivery_id)
                
                for delivery_id in expired_ids:
                    del self.delivery_records[delivery_id]
            
            logger.info(f"Cleaned up {len(expired_ids)} old delivery records")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {str(e)}")

class DeliveryAnalytics:
    """Analytics for delivery tracking"""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: defaultdict(int))
        self.performance_data = defaultdict(list)
    
    def record_delivery_event(self, record: DeliveryRecord, attempt: DeliveryAttempt):
        """Record delivery event for analytics"""
        date_key = record.updated_at.strftime('%Y-%m-%d')
        channel_key = record.channel.value
        status_key = attempt.status.value
        
        # Update metrics
        self.metrics[date_key][f"{channel_key}_{status_key}"] += 1
        self.metrics[date_key][f"total_{status_key}"] += 1
        self.metrics[date_key]["total_attempts"] += 1
        
        # Record performance data
        if attempt.duration_ms:
            self.performance_data[channel_key].append({
                'timestamp': attempt.timestamp,
                'duration_ms': attempt.duration_ms,
                'status': status_key
            })
    
    def get_analytics(self, start_date: datetime = None, end_date: datetime = None) -> Dict:
        """Get delivery analytics"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()
        
        analytics = {
            'summary': defaultdict(int),
            'by_channel': defaultdict(lambda: defaultdict(int)),
            'by_date': defaultdict(lambda: defaultdict(int)),
            'performance': {}
        }
        
        # Process metrics within date range
        current_date = start_date
        while current_date <= end_date:
            date_key = current_date.strftime('%Y-%m-%d')
            date_metrics = self.metrics.get(date_key, {})
            
            for metric_key, value in date_metrics.items():
                if '_' in metric_key:
                    channel, status = metric_key.split('_', 1)
                    if channel != 'total':
                        analytics['by_channel'][channel][status] += value
                        analytics['summary'][status] += value
                
                analytics['by_date'][date_key][metric_key] = value
            
            current_date += timedelta(days=1)
        
        # Calculate performance metrics
        for channel, perf_data in self.performance_data.items():
            if perf_data:
                durations = [d['duration_ms'] for d in perf_data if d['duration_ms']]
                if durations:
                    analytics['performance'][channel] = {
                        'avg_duration_ms': sum(durations) / len(durations),
                        'min_duration_ms': min(durations),
                        'max_duration_ms': max(durations),
                        'total_requests': len(perf_data)
                    }
        
        return dict(analytics)
    
    def get_channel_performance(self, channel: DeliveryChannel,
                               start_date: datetime = None,
                               end_date: datetime = None) -> Dict:
        """Get performance metrics for specific channel"""
        channel_key = channel.value
        perf_data = self.performance_data.get(channel_key, [])
        
        if not perf_data:
            return {}
        
        # Filter by date range if provided
        if start_date or end_date:
            filtered_data = []
            for data_point in perf_data:
                timestamp = data_point['timestamp']
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue
                filtered_data.append(data_point)
            perf_data = filtered_data
        
        if not perf_data:
            return {}
        
        # Calculate metrics
        durations = [d['duration_ms'] for d in perf_data if d['duration_ms']]
        success_count = len([d for d in perf_data if d['status'] in ['sent', 'delivered']])
        
        return {
            'total_requests': len(perf_data),
            'success_count': success_count,
            'success_rate': success_count / len(perf_data) if perf_data else 0,
            'avg_duration_ms': sum(durations) / len(durations) if durations else 0,
            'min_duration_ms': min(durations) if durations else 0,
            'max_duration_ms': max(durations) if durations else 0,
            'p95_duration_ms': self._calculate_percentile(durations, 95) if durations else 0,
            'p99_duration_ms': self._calculate_percentile(durations, 99) if durations else 0
        }
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]
