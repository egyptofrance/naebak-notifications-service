#!/usr/bin/env python3
"""
Naebak Notifications Service - Analytics Module
===============================================

Comprehensive analytics system for tracking notification performance,
delivery rates, user engagement, and system metrics.

Features:
- Real-time metrics collection
- Delivery rate analytics
- Channel performance comparison
- User engagement tracking
- Error analysis and reporting
- Performance monitoring
- Custom dashboards
- Export capabilities
"""

import time
import json
import redis
import logging
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
import threading
from config import Config

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of metrics to track"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

class TimeRange(Enum):
    """Time range options for analytics"""
    HOUR = "1h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1m"
    QUARTER = "3m"
    YEAR = "1y"

@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    labels: Dict[str, str]
    metric_name: str

@dataclass
class AnalyticsReport:
    """Analytics report structure"""
    period: str
    start_date: datetime
    end_date: datetime
    total_notifications: int
    delivery_rate: float
    channel_breakdown: Dict[str, Dict[str, Any]]
    error_analysis: Dict[str, int]
    performance_metrics: Dict[str, float]
    trends: Dict[str, List[float]]
    recommendations: List[str]

class MetricsCollector:
    """Collects and stores metrics"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB
        )
        self.metrics_buffer = defaultdict(list)
        self.buffer_lock = threading.Lock()
        
        # Start background flush thread
        self._start_flush_thread()
    
    def increment_counter(self, metric_name: str, value: float = 1.0, 
                         labels: Dict[str, str] = None):
        """Increment a counter metric"""
        self._add_metric(metric_name, MetricType.COUNTER, value, labels)
    
    def set_gauge(self, metric_name: str, value: float, 
                  labels: Dict[str, str] = None):
        """Set a gauge metric value"""
        self._add_metric(metric_name, MetricType.GAUGE, value, labels)
    
    def record_histogram(self, metric_name: str, value: float,
                        labels: Dict[str, str] = None):
        """Record a histogram value"""
        self._add_metric(metric_name, MetricType.HISTOGRAM, value, labels)
    
    def record_timer(self, metric_name: str, duration_ms: float,
                    labels: Dict[str, str] = None):
        """Record a timer value"""
        self._add_metric(metric_name, MetricType.TIMER, duration_ms, labels)
    
    def _add_metric(self, metric_name: str, metric_type: MetricType, 
                   value: float, labels: Dict[str, str] = None):
        """Add metric to buffer"""
        metric_point = MetricPoint(
            timestamp=datetime.utcnow(),
            value=value,
            labels=labels or {},
            metric_name=metric_name
        )
        
        with self.buffer_lock:
            self.metrics_buffer[metric_type].append(metric_point)
    
    def _start_flush_thread(self):
        """Start background thread to flush metrics to Redis"""
        def flush_worker():
            while True:
                try:
                    self._flush_metrics()
                    time.sleep(10)  # Flush every 10 seconds
                except Exception as e:
                    logger.error(f"Metrics flush error: {str(e)}")
                    time.sleep(30)
        
        flush_thread = threading.Thread(target=flush_worker, daemon=True)
        flush_thread.start()
    
    def _flush_metrics(self):
        """Flush buffered metrics to Redis"""
        with self.buffer_lock:
            if not any(self.metrics_buffer.values()):
                return
            
            # Copy and clear buffer
            metrics_to_flush = dict(self.metrics_buffer)
            self.metrics_buffer.clear()
        
        # Store metrics in Redis
        for metric_type, metrics in metrics_to_flush.items():
            for metric in metrics:
                self._store_metric_in_redis(metric, metric_type)
    
    def _store_metric_in_redis(self, metric: MetricPoint, metric_type: MetricType):
        """Store single metric in Redis"""
        try:
            # Create time-based keys for efficient querying
            timestamp_key = metric.timestamp.strftime('%Y%m%d%H%M')
            hour_key = metric.timestamp.strftime('%Y%m%d%H')
            day_key = metric.timestamp.strftime('%Y%m%d')
            
            # Create metric key with labels
            labels_str = "_".join([f"{k}:{v}" for k, v in sorted(metric.labels.items())])
            metric_key = f"{metric.metric_name}_{labels_str}" if labels_str else metric.metric_name
            
            # Store in different time granularities
            pipe = self.redis_client.pipeline()
            
            # Minute-level data (kept for 24 hours)
            minute_key = f"metrics:minute:{day_key}:{metric_key}"
            pipe.zadd(minute_key, {timestamp_key: metric.value})
            pipe.expire(minute_key, 86400)  # 24 hours
            
            # Hour-level aggregation (kept for 30 days)
            hour_key_redis = f"metrics:hour:{day_key[:6]}:{metric_key}"
            if metric_type == MetricType.COUNTER:
                pipe.zincrby(hour_key_redis, metric.value, hour_key)
            else:
                # For gauges, histograms, timers - store latest value
                pipe.zadd(hour_key_redis, {hour_key: metric.value})
            pipe.expire(hour_key_redis, 86400 * 30)  # 30 days
            
            # Daily aggregation (kept for 1 year)
            daily_key = f"metrics:daily:{day_key[:4]}:{metric_key}"
            if metric_type == MetricType.COUNTER:
                pipe.zincrby(daily_key, metric.value, day_key)
            else:
                pipe.zadd(daily_key, {day_key: metric.value})
            pipe.expire(daily_key, 86400 * 365)  # 1 year
            
            pipe.execute()
            
        except Exception as e:
            logger.error(f"Failed to store metric in Redis: {str(e)}")

class NotificationAnalytics:
    """Main analytics class for notifications"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB
        )
        self.metrics_collector = MetricsCollector(self.redis_client)
        
        # Metric names
        self.METRICS = {
            'notifications_sent': 'notifications_sent_total',
            'notifications_delivered': 'notifications_delivered_total',
            'notifications_failed': 'notifications_failed_total',
            'notifications_read': 'notifications_read_total',
            'delivery_time': 'notification_delivery_time_ms',
            'channel_usage': 'notification_channel_usage',
            'error_count': 'notification_errors_total',
            'user_engagement': 'user_engagement_score'
        }
    
    def track_notification_sent(self, user_id: str, channel: str, 
                               template_id: str, success: bool = True):
        """Track notification sent event"""
        labels = {
            'channel': channel,
            'template_id': template_id,
            'user_id': user_id
        }
        
        self.metrics_collector.increment_counter(
            self.METRICS['notifications_sent'], 1.0, labels
        )
        
        if success:
            self.metrics_collector.increment_counter(
                self.METRICS['channel_usage'], 1.0, {'channel': channel}
            )
        else:
            self.metrics_collector.increment_counter(
                self.METRICS['notifications_failed'], 1.0, labels
            )
    
    def track_notification_delivered(self, user_id: str, channel: str,
                                   delivery_time_ms: float):
        """Track notification delivery"""
        labels = {
            'channel': channel,
            'user_id': user_id
        }
        
        self.metrics_collector.increment_counter(
            self.METRICS['notifications_delivered'], 1.0, labels
        )
        
        self.metrics_collector.record_timer(
            self.METRICS['delivery_time'], delivery_time_ms, labels
        )
    
    def track_notification_read(self, user_id: str, channel: str,
                               time_to_read_ms: float):
        """Track notification read event"""
        labels = {
            'channel': channel,
            'user_id': user_id
        }
        
        self.metrics_collector.increment_counter(
            self.METRICS['notifications_read'], 1.0, labels
        )
        
        # Calculate engagement score based on read time
        engagement_score = self._calculate_engagement_score(time_to_read_ms)
        self.metrics_collector.record_histogram(
            self.METRICS['user_engagement'], engagement_score, labels
        )
    
    def track_notification_error(self, channel: str, error_type: str,
                                error_message: str = None):
        """Track notification error"""
        labels = {
            'channel': channel,
            'error_type': error_type
        }
        
        self.metrics_collector.increment_counter(
            self.METRICS['error_count'], 1.0, labels
        )
    
    def track_delivery_event(self, record, attempt):
        """Track delivery event from delivery tracker"""
        labels = {
            'channel': record.channel.value,
            'status': attempt.status.value,
            'user_id': record.user_id
        }
        
        if attempt.status.value in ['sent', 'delivered']:
            self.track_notification_delivered(
                record.user_id,
                record.channel.value,
                attempt.duration_ms or 0
            )
        elif attempt.status.value == 'failed':
            self.track_notification_error(
                record.channel.value,
                record.failure_reason.value if record.failure_reason else 'unknown',
                attempt.error_message
            )
        elif attempt.status.value == 'read':
            # Calculate time from delivery to read
            if record.delivered_at and record.read_at:
                time_to_read = (record.read_at - record.delivered_at).total_seconds() * 1000
                self.track_notification_read(
                    record.user_id,
                    record.channel.value,
                    time_to_read
                )
    
    def get_analytics(self, start_date: datetime = None, 
                     end_date: datetime = None) -> AnalyticsReport:
        """Get comprehensive analytics report"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get basic metrics
        total_sent = self._get_metric_sum(
            self.METRICS['notifications_sent'], start_date, end_date
        )
        total_delivered = self._get_metric_sum(
            self.METRICS['notifications_delivered'], start_date, end_date
        )
        total_failed = self._get_metric_sum(
            self.METRICS['notifications_failed'], start_date, end_date
        )
        total_read = self._get_metric_sum(
            self.METRICS['notifications_read'], start_date, end_date
        )
        
        # Calculate delivery rate
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Get channel breakdown
        channel_breakdown = self._get_channel_breakdown(start_date, end_date)
        
        # Get error analysis
        error_analysis = self._get_error_analysis(start_date, end_date)
        
        # Get performance metrics
        performance_metrics = self._get_performance_metrics(start_date, end_date)
        
        # Get trends
        trends = self._get_trends(start_date, end_date)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            delivery_rate, channel_breakdown, error_analysis, performance_metrics
        )
        
        return AnalyticsReport(
            period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            start_date=start_date,
            end_date=end_date,
            total_notifications=int(total_sent),
            delivery_rate=round(delivery_rate, 2),
            channel_breakdown=channel_breakdown,
            error_analysis=error_analysis,
            performance_metrics=performance_metrics,
            trends=trends,
            recommendations=recommendations
        )
    
    def get_channel_performance(self, channel: str, start_date: datetime = None,
                               end_date: datetime = None) -> Dict[str, Any]:
        """Get performance metrics for specific channel"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get channel-specific metrics
        sent = self._get_metric_sum(
            self.METRICS['notifications_sent'], start_date, end_date, {'channel': channel}
        )
        delivered = self._get_metric_sum(
            self.METRICS['notifications_delivered'], start_date, end_date, {'channel': channel}
        )
        failed = self._get_metric_sum(
            self.METRICS['notifications_failed'], start_date, end_date, {'channel': channel}
        )
        read = self._get_metric_sum(
            self.METRICS['notifications_read'], start_date, end_date, {'channel': channel}
        )
        
        # Get delivery times
        delivery_times = self._get_metric_values(
            self.METRICS['delivery_time'], start_date, end_date, {'channel': channel}
        )
        
        # Calculate metrics
        delivery_rate = (delivered / sent * 100) if sent > 0 else 0
        read_rate = (read / delivered * 100) if delivered > 0 else 0
        failure_rate = (failed / sent * 100) if sent > 0 else 0
        
        avg_delivery_time = statistics.mean(delivery_times) if delivery_times else 0
        p95_delivery_time = self._calculate_percentile(delivery_times, 95) if delivery_times else 0
        
        return {
            'channel': channel,
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'total_sent': int(sent),
            'total_delivered': int(delivered),
            'total_failed': int(failed),
            'total_read': int(read),
            'delivery_rate': round(delivery_rate, 2),
            'read_rate': round(read_rate, 2),
            'failure_rate': round(failure_rate, 2),
            'avg_delivery_time_ms': round(avg_delivery_time, 2),
            'p95_delivery_time_ms': round(p95_delivery_time, 2),
            'performance_score': self._calculate_channel_score(
                delivery_rate, read_rate, avg_delivery_time
            )
        }
    
    def get_user_engagement_metrics(self, user_id: str = None,
                                   start_date: datetime = None,
                                   end_date: datetime = None) -> Dict[str, Any]:
        """Get user engagement metrics"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        labels = {'user_id': user_id} if user_id else {}
        
        # Get engagement scores
        engagement_scores = self._get_metric_values(
            self.METRICS['user_engagement'], start_date, end_date, labels
        )
        
        # Get notification counts
        sent = self._get_metric_sum(
            self.METRICS['notifications_sent'], start_date, end_date, labels
        )
        read = self._get_metric_sum(
            self.METRICS['notifications_read'], start_date, end_date, labels
        )
        
        avg_engagement = statistics.mean(engagement_scores) if engagement_scores else 0
        read_rate = (read / sent * 100) if sent > 0 else 0
        
        return {
            'user_id': user_id,
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'total_notifications_received': int(sent),
            'total_notifications_read': int(read),
            'read_rate': round(read_rate, 2),
            'avg_engagement_score': round(avg_engagement, 2),
            'engagement_level': self._classify_engagement_level(avg_engagement)
        }
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics for dashboard"""
        now = datetime.utcnow()
        last_hour = now - timedelta(hours=1)
        
        # Get last hour metrics
        sent_last_hour = self._get_metric_sum(
            self.METRICS['notifications_sent'], last_hour, now
        )
        delivered_last_hour = self._get_metric_sum(
            self.METRICS['notifications_delivered'], last_hour, now
        )
        failed_last_hour = self._get_metric_sum(
            self.METRICS['notifications_failed'], last_hour, now
        )
        
        # Get current rates (per minute)
        last_minute = now - timedelta(minutes=1)
        sent_last_minute = self._get_metric_sum(
            self.METRICS['notifications_sent'], last_minute, now
        )
        
        return {
            'timestamp': now.isoformat(),
            'last_hour': {
                'sent': int(sent_last_hour),
                'delivered': int(delivered_last_hour),
                'failed': int(failed_last_hour),
                'delivery_rate': round((delivered_last_hour / sent_last_hour * 100) if sent_last_hour > 0 else 0, 2)
            },
            'current_rate': {
                'notifications_per_minute': int(sent_last_minute),
                'notifications_per_hour': int(sent_last_minute * 60)
            },
            'system_health': self._get_system_health_score()
        }
    
    def _get_metric_sum(self, metric_name: str, start_date: datetime,
                       end_date: datetime, labels: Dict[str, str] = None) -> float:
        """Get sum of metric values in time range"""
        try:
            # Build metric key with labels
            labels_str = "_".join([f"{k}:{v}" for k, v in sorted(labels.items())]) if labels else ""
            metric_key = f"{metric_name}_{labels_str}" if labels_str else metric_name
            
            # Determine appropriate time granularity
            time_diff = end_date - start_date
            if time_diff <= timedelta(hours=24):
                # Use minute-level data
                redis_key = f"metrics:minute:{start_date.strftime('%Y%m%d')}:{metric_key}"
                start_score = start_date.strftime('%Y%m%d%H%M')
                end_score = end_date.strftime('%Y%m%d%H%M')
            elif time_diff <= timedelta(days=30):
                # Use hour-level data
                redis_key = f"metrics:hour:{start_date.strftime('%Y%m')}:{metric_key}"
                start_score = start_date.strftime('%Y%m%d%H')
                end_score = end_date.strftime('%Y%m%d%H')
            else:
                # Use daily data
                redis_key = f"metrics:daily:{start_date.strftime('%Y')}:{metric_key}"
                start_score = start_date.strftime('%Y%m%d')
                end_score = end_date.strftime('%Y%m%d')
            
            # Get values from Redis
            values = self.redis_client.zrangebyscore(redis_key, start_score, end_score, withscores=True)
            return sum(score for _, score in values)
            
        except Exception as e:
            logger.error(f"Failed to get metric sum: {str(e)}")
            return 0.0
    
    def _get_metric_values(self, metric_name: str, start_date: datetime,
                          end_date: datetime, labels: Dict[str, str] = None) -> List[float]:
        """Get list of metric values in time range"""
        try:
            labels_str = "_".join([f"{k}:{v}" for k, v in sorted(labels.items())]) if labels else ""
            metric_key = f"{metric_name}_{labels_str}" if labels_str else metric_name
            
            redis_key = f"metrics:minute:{start_date.strftime('%Y%m%d')}:{metric_key}"
            start_score = start_date.strftime('%Y%m%d%H%M')
            end_score = end_date.strftime('%Y%m%d%H%M')
            
            values = self.redis_client.zrangebyscore(redis_key, start_score, end_score, withscores=True)
            return [score for _, score in values]
            
        except Exception as e:
            logger.error(f"Failed to get metric values: {str(e)}")
            return []
    
    def _get_channel_breakdown(self, start_date: datetime, end_date: datetime) -> Dict[str, Dict[str, Any]]:
        """Get breakdown by channel"""
        channels = ['email', 'sms', 'push', 'in_app', 'webhook']
        breakdown = {}
        
        for channel in channels:
            performance = self.get_channel_performance(channel, start_date, end_date)
            if performance['total_sent'] > 0:
                breakdown[channel] = performance
        
        return breakdown
    
    def _get_error_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get error analysis"""
        # This would typically query error metrics by type
        # For now, return sample data
        return {
            'network_error': 5,
            'authentication_failed': 2,
            'rate_limited': 8,
            'invalid_recipient': 12,
            'service_unavailable': 3
        }
    
    def _get_performance_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """Get performance metrics"""
        delivery_times = self._get_metric_values(
            self.METRICS['delivery_time'], start_date, end_date
        )
        
        if not delivery_times:
            return {}
        
        return {
            'avg_delivery_time_ms': round(statistics.mean(delivery_times), 2),
            'median_delivery_time_ms': round(statistics.median(delivery_times), 2),
            'p95_delivery_time_ms': round(self._calculate_percentile(delivery_times, 95), 2),
            'p99_delivery_time_ms': round(self._calculate_percentile(delivery_times, 99), 2),
            'min_delivery_time_ms': round(min(delivery_times), 2),
            'max_delivery_time_ms': round(max(delivery_times), 2)
        }
    
    def _get_trends(self, start_date: datetime, end_date: datetime) -> Dict[str, List[float]]:
        """Get trend data"""
        # Generate daily trends
        trends = {}
        current_date = start_date
        
        sent_trend = []
        delivered_trend = []
        failed_trend = []
        
        while current_date <= end_date:
            day_start = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            daily_sent = self._get_metric_sum(
                self.METRICS['notifications_sent'], day_start, day_end
            )
            daily_delivered = self._get_metric_sum(
                self.METRICS['notifications_delivered'], day_start, day_end
            )
            daily_failed = self._get_metric_sum(
                self.METRICS['notifications_failed'], day_start, day_end
            )
            
            sent_trend.append(daily_sent)
            delivered_trend.append(daily_delivered)
            failed_trend.append(daily_failed)
            
            current_date += timedelta(days=1)
        
        trends['sent'] = sent_trend
        trends['delivered'] = delivered_trend
        trends['failed'] = failed_trend
        
        return trends
    
    def _generate_recommendations(self, delivery_rate: float, 
                                 channel_breakdown: Dict[str, Dict[str, Any]],
                                 error_analysis: Dict[str, int],
                                 performance_metrics: Dict[str, float]) -> List[str]:
        """Generate recommendations based on analytics"""
        recommendations = []
        
        # Delivery rate recommendations
        if delivery_rate < 90:
            recommendations.append("تحسين معدل التسليم: معدل التسليم أقل من 90%. راجع إعدادات الخدمات الخارجية.")
        
        # Channel performance recommendations
        for channel, metrics in channel_breakdown.items():
            if metrics['failure_rate'] > 10:
                recommendations.append(f"قناة {channel}: معدل فشل عالي ({metrics['failure_rate']:.1f}%). راجع التكوين.")
            
            if metrics['avg_delivery_time_ms'] > 5000:
                recommendations.append(f"قناة {channel}: وقت التسليم بطيء ({metrics['avg_delivery_time_ms']:.0f}ms). حسّن الأداء.")
        
        # Error analysis recommendations
        if error_analysis.get('rate_limited', 0) > 5:
            recommendations.append("تحديد المعدل: عدد كبير من أخطاء تحديد المعدل. قلل من معدل الإرسال.")
        
        if error_analysis.get('invalid_recipient', 0) > 10:
            recommendations.append("المستقبلون غير صالحون: تحقق من صحة بيانات المستخدمين.")
        
        # Performance recommendations
        if performance_metrics.get('p95_delivery_time_ms', 0) > 10000:
            recommendations.append("الأداء: 95% من الإشعارات تستغرق أكثر من 10 ثوانٍ. حسّن البنية التحتية.")
        
        if not recommendations:
            recommendations.append("الأداء ممتاز! جميع المقاييس ضمن النطاقات المقبولة.")
        
        return recommendations
    
    def _calculate_engagement_score(self, time_to_read_ms: float) -> float:
        """Calculate engagement score based on read time"""
        # Quick reads (< 1 minute) = high engagement
        # Medium reads (1-10 minutes) = medium engagement
        # Slow reads (> 10 minutes) = low engagement
        
        time_minutes = time_to_read_ms / (1000 * 60)
        
        if time_minutes < 1:
            return 100.0
        elif time_minutes < 10:
            return max(50.0, 100.0 - (time_minutes - 1) * 5.5)
        else:
            return max(10.0, 50.0 - (time_minutes - 10) * 2)
    
    def _calculate_channel_score(self, delivery_rate: float, read_rate: float,
                                avg_delivery_time: float) -> float:
        """Calculate overall channel performance score"""
        # Weighted score: 50% delivery rate, 30% read rate, 20% speed
        delivery_score = delivery_rate
        read_score = read_rate
        speed_score = max(0, 100 - (avg_delivery_time / 1000))  # Penalize slow delivery
        
        return round(delivery_score * 0.5 + read_score * 0.3 + speed_score * 0.2, 2)
    
    def _classify_engagement_level(self, avg_engagement: float) -> str:
        """Classify engagement level"""
        if avg_engagement >= 80:
            return "عالي"
        elif avg_engagement >= 50:
            return "متوسط"
        else:
            return "منخفض"
    
    def _get_system_health_score(self) -> float:
        """Calculate system health score"""
        # This would typically check various system metrics
        # For now, return a sample score
        return 95.5
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def export_analytics(self, report: AnalyticsReport, format: str = 'json') -> str:
        """Export analytics report"""
        if format == 'json':
            return json.dumps(asdict(report), default=str, ensure_ascii=False, indent=2)
        elif format == 'csv':
            # Convert to CSV format
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers and data
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Period', report.period])
            writer.writerow(['Total Notifications', report.total_notifications])
            writer.writerow(['Delivery Rate', f"{report.delivery_rate}%"])
            
            # Channel breakdown
            for channel, metrics in report.channel_breakdown.items():
                writer.writerow([f'{channel} - Sent', metrics['total_sent']])
                writer.writerow([f'{channel} - Delivered', metrics['total_delivered']])
                writer.writerow([f'{channel} - Delivery Rate', f"{metrics['delivery_rate']}%"])
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")

# Global analytics instance
notification_analytics = NotificationAnalytics()

def get_analytics_dashboard_data() -> Dict[str, Any]:
    """Get data for analytics dashboard"""
    now = datetime.utcnow()
    
    # Get different time ranges
    last_24h = notification_analytics.get_analytics(
        now - timedelta(days=1), now
    )
    last_7d = notification_analytics.get_analytics(
        now - timedelta(days=7), now
    )
    last_30d = notification_analytics.get_analytics(
        now - timedelta(days=30), now
    )
    
    # Get real-time metrics
    real_time = notification_analytics.get_real_time_metrics()
    
    return {
        'real_time': real_time,
        'last_24h': asdict(last_24h),
        'last_7d': asdict(last_7d),
        'last_30d': asdict(last_30d),
        'timestamp': now.isoformat()
    }
