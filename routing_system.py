#!/usr/bin/env python3
"""
Naebak Notifications Service - Routing System
=============================================

Advanced routing system for handling notification requests with load balancing,
service discovery, health checking, and intelligent request distribution.

Features:
- Dynamic service discovery
- Load balancing algorithms
- Health monitoring
- Circuit breaker pattern
- Request routing and forwarding
- Failover mechanisms
- Performance monitoring
"""

import time
import random
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, deque
from enum import Enum
import threading
import json
from dataclasses import dataclass, asdict
from config import Config

logger = logging.getLogger(__name__)

class LoadBalancingAlgorithm(Enum):
    """Load balancing algorithms"""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    RANDOM = "random"
    HASH = "hash"

class ServiceStatus(Enum):
    """Service status enumeration"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"

@dataclass
class ServiceEndpoint:
    """Service endpoint information"""
    id: str
    host: str
    port: int
    protocol: str = "http"
    weight: int = 1
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_health_check: Optional[datetime] = None
    response_time_ms: float = 0.0
    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 100.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def url(self) -> str:
        """Get full URL for the endpoint"""
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def is_healthy(self) -> bool:
        """Check if endpoint is healthy"""
        return self.status == ServiceStatus.HEALTHY

@dataclass
class RouteRule:
    """Route rule configuration"""
    path_pattern: str
    service_name: str
    method: str = "GET"
    headers: Dict[str, str] = None
    query_params: Dict[str, str] = None
    timeout: int = 30
    retries: int = 3
    circuit_breaker_enabled: bool = True
    load_balancing: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.query_params is None:
            self.query_params = {}

class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        with self.lock:
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if self.last_failure_time is None:
            return True
        
        return (datetime.utcnow() - self.last_failure_time).total_seconds() > self.recovery_timeout
    
    def _on_success(self):
        """Handle successful request"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

class ServiceRegistry:
    """Service registry for managing service endpoints"""
    
    def __init__(self):
        self.services: Dict[str, List[ServiceEndpoint]] = defaultdict(list)
        self.route_rules: Dict[str, RouteRule] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.lock = threading.Lock()
        
        # Load balancing state
        self.round_robin_counters: Dict[str, int] = defaultdict(int)
        
        # Start health check thread
        self._start_health_check_thread()
    
    def register_service(self, service_name: str, endpoint: ServiceEndpoint):
        """Register a service endpoint"""
        with self.lock:
            self.services[service_name].append(endpoint)
            logger.info(f"Registered service endpoint: {service_name} -> {endpoint.url}")
    
    def unregister_service(self, service_name: str, endpoint_id: str):
        """Unregister a service endpoint"""
        with self.lock:
            endpoints = self.services.get(service_name, [])
            self.services[service_name] = [ep for ep in endpoints if ep.id != endpoint_id]
            logger.info(f"Unregistered service endpoint: {service_name} -> {endpoint_id}")
    
    def add_route_rule(self, path: str, rule: RouteRule):
        """Add a routing rule"""
        self.route_rules[path] = rule
        logger.info(f"Added route rule: {path} -> {rule.service_name}")
    
    def get_healthy_endpoints(self, service_name: str) -> List[ServiceEndpoint]:
        """Get healthy endpoints for a service"""
        with self.lock:
            endpoints = self.services.get(service_name, [])
            return [ep for ep in endpoints if ep.is_healthy]
    
    def select_endpoint(self, service_name: str, 
                       algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN,
                       request_hash: str = None) -> Optional[ServiceEndpoint]:
        """Select an endpoint using specified load balancing algorithm"""
        healthy_endpoints = self.get_healthy_endpoints(service_name)
        
        if not healthy_endpoints:
            logger.warning(f"No healthy endpoints available for service: {service_name}")
            return None
        
        if algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            return self._round_robin_select(service_name, healthy_endpoints)
        elif algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(healthy_endpoints)
        elif algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return self._least_connections_select(healthy_endpoints)
        elif algorithm == LoadBalancingAlgorithm.LEAST_RESPONSE_TIME:
            return self._least_response_time_select(healthy_endpoints)
        elif algorithm == LoadBalancingAlgorithm.RANDOM:
            return random.choice(healthy_endpoints)
        elif algorithm == LoadBalancingAlgorithm.HASH:
            return self._hash_select(healthy_endpoints, request_hash or "")
        else:
            return healthy_endpoints[0]
    
    def _round_robin_select(self, service_name: str, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Round robin selection"""
        with self.lock:
            counter = self.round_robin_counters[service_name]
            selected = endpoints[counter % len(endpoints)]
            self.round_robin_counters[service_name] = (counter + 1) % len(endpoints)
            return selected
    
    def _weighted_round_robin_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Weighted round robin selection"""
        total_weight = sum(ep.weight for ep in endpoints)
        random_weight = random.randint(1, total_weight)
        
        current_weight = 0
        for endpoint in endpoints:
            current_weight += endpoint.weight
            if random_weight <= current_weight:
                return endpoint
        
        return endpoints[0]
    
    def _least_connections_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Least connections selection"""
        return min(endpoints, key=lambda ep: ep.active_connections)
    
    def _least_response_time_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Least response time selection"""
        return min(endpoints, key=lambda ep: ep.response_time_ms)
    
    def _hash_select(self, endpoints: List[ServiceEndpoint], hash_key: str) -> ServiceEndpoint:
        """Hash-based selection"""
        hash_value = hash(hash_key)
        index = hash_value % len(endpoints)
        return endpoints[index]
    
    def update_endpoint_stats(self, service_name: str, endpoint_id: str,
                             response_time_ms: float, success: bool):
        """Update endpoint statistics"""
        with self.lock:
            for endpoint in self.services.get(service_name, []):
                if endpoint.id == endpoint_id:
                    endpoint.response_time_ms = response_time_ms
                    endpoint.total_requests += 1
                    
                    if not success:
                        endpoint.failed_requests += 1
                    
                    # Calculate success rate
                    if endpoint.total_requests > 0:
                        endpoint.success_rate = ((endpoint.total_requests - endpoint.failed_requests) / 
                                               endpoint.total_requests) * 100
                    
                    break
    
    def _start_health_check_thread(self):
        """Start background health check thread"""
        def health_check_worker():
            while True:
                try:
                    self._perform_health_checks()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    logger.error(f"Health check error: {str(e)}")
                    time.sleep(60)
        
        health_thread = threading.Thread(target=health_check_worker, daemon=True)
        health_thread.start()
    
    def _perform_health_checks(self):
        """Perform health checks on all endpoints"""
        with self.lock:
            services_copy = dict(self.services)
        
        for service_name, endpoints in services_copy.items():
            for endpoint in endpoints:
                try:
                    self._check_endpoint_health(endpoint)
                except Exception as e:
                    logger.error(f"Health check failed for {endpoint.url}: {str(e)}")
                    endpoint.status = ServiceStatus.UNHEALTHY
    
    def _check_endpoint_health(self, endpoint: ServiceEndpoint):
        """Check health of a single endpoint"""
        health_url = f"{endpoint.url}/health"
        start_time = time.time()
        
        try:
            response = requests.get(health_url, timeout=5)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                endpoint.status = ServiceStatus.HEALTHY
                endpoint.response_time_ms = response_time
            else:
                endpoint.status = ServiceStatus.UNHEALTHY
            
            endpoint.last_health_check = datetime.utcnow()
            
        except requests.exceptions.RequestException:
            endpoint.status = ServiceStatus.UNHEALTHY
            endpoint.last_health_check = datetime.utcnow()

class NotificationRouter:
    """Main notification routing system"""
    
    def __init__(self):
        self.service_registry = ServiceRegistry()
        self.request_history = deque(maxlen=1000)
        self.performance_metrics = defaultdict(list)
        
        # Initialize default services
        self._initialize_default_services()
        self._setup_default_routes()
    
    def _initialize_default_services(self):
        """Initialize default notification services"""
        # Email service endpoints
        email_endpoints = [
            ServiceEndpoint("email-1", "localhost", 5001, weight=2),
            ServiceEndpoint("email-2", "localhost", 5002, weight=1)
        ]
        
        for endpoint in email_endpoints:
            self.service_registry.register_service("email-service", endpoint)
        
        # SMS service endpoints
        sms_endpoints = [
            ServiceEndpoint("sms-1", "localhost", 5003, weight=1),
            ServiceEndpoint("sms-2", "localhost", 5004, weight=1)
        ]
        
        for endpoint in sms_endpoints:
            self.service_registry.register_service("sms-service", endpoint)
        
        # Push notification service endpoints
        push_endpoints = [
            ServiceEndpoint("push-1", "localhost", 5005, weight=3),
            ServiceEndpoint("push-2", "localhost", 5006, weight=2)
        ]
        
        for endpoint in push_endpoints:
            self.service_registry.register_service("push-service", endpoint)
        
        # In-app notification service
        in_app_endpoint = ServiceEndpoint("in-app-1", "localhost", 5007, weight=1)
        self.service_registry.register_service("in-app-service", in_app_endpoint)
        
        # Webhook service
        webhook_endpoint = ServiceEndpoint("webhook-1", "localhost", 5008, weight=1)
        self.service_registry.register_service("webhook-service", webhook_endpoint)
    
    def _setup_default_routes(self):
        """Setup default routing rules"""
        routes = [
            ("/api/v1/notifications/email", RouteRule(
                "/api/v1/notifications/email",
                "email-service",
                method="POST",
                load_balancing=LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN
            )),
            ("/api/v1/notifications/sms", RouteRule(
                "/api/v1/notifications/sms",
                "sms-service",
                method="POST",
                load_balancing=LoadBalancingAlgorithm.LEAST_RESPONSE_TIME
            )),
            ("/api/v1/notifications/push", RouteRule(
                "/api/v1/notifications/push",
                "push-service",
                method="POST",
                load_balancing=LoadBalancingAlgorithm.ROUND_ROBIN
            )),
            ("/api/v1/notifications/in-app", RouteRule(
                "/api/v1/notifications/in-app",
                "in-app-service",
                method="POST"
            )),
            ("/api/v1/notifications/webhook", RouteRule(
                "/api/v1/notifications/webhook",
                "webhook-service",
                method="POST"
            ))
        ]
        
        for path, rule in routes:
            self.service_registry.add_route_rule(path, rule)
    
    def route_request(self, path: str, method: str = "GET", 
                     headers: Dict[str, str] = None,
                     data: Any = None, params: Dict[str, str] = None) -> Tuple[bool, Any]:
        """Route a request to appropriate service"""
        # Find matching route rule
        route_rule = self._find_route_rule(path, method)
        if not route_rule:
            logger.warning(f"No route rule found for {method} {path}")
            return False, {"error": "Route not found", "status_code": 404}
        
        # Select endpoint
        endpoint = self.service_registry.select_endpoint(
            route_rule.service_name,
            route_rule.load_balancing,
            self._generate_request_hash(headers, data)
        )
        
        if not endpoint:
            logger.error(f"No healthy endpoints available for {route_rule.service_name}")
            return False, {"error": "Service unavailable", "status_code": 503}
        
        # Execute request with circuit breaker
        circuit_breaker = self._get_circuit_breaker(route_rule.service_name)
        
        try:
            if route_rule.circuit_breaker_enabled:
                result = circuit_breaker.call(
                    self._execute_request,
                    endpoint, path, method, headers, data, params, route_rule
                )
            else:
                result = self._execute_request(
                    endpoint, path, method, headers, data, params, route_rule
                )
            
            return True, result
            
        except Exception as e:
            logger.error(f"Request failed for {endpoint.url}{path}: {str(e)}")
            return False, {"error": str(e), "status_code": 500}
    
    def _find_route_rule(self, path: str, method: str) -> Optional[RouteRule]:
        """Find matching route rule for path and method"""
        # Exact match first
        for rule_path, rule in self.service_registry.route_rules.items():
            if rule_path == path and rule.method == method:
                return rule
        
        # Pattern matching (simple prefix matching for now)
        for rule_path, rule in self.service_registry.route_rules.items():
            if path.startswith(rule_path.rstrip('*')) and rule.method == method:
                return rule
        
        return None
    
    def _generate_request_hash(self, headers: Dict[str, str] = None, data: Any = None) -> str:
        """Generate hash for request routing"""
        hash_components = []
        
        if headers:
            user_id = headers.get('X-User-ID')
            if user_id:
                hash_components.append(user_id)
        
        if data and isinstance(data, dict):
            recipient = data.get('recipient')
            if recipient:
                hash_components.append(recipient)
        
        return '|'.join(hash_components) if hash_components else ""
    
    def _get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.service_registry.circuit_breakers:
            self.service_registry.circuit_breakers[service_name] = CircuitBreaker()
        
        return self.service_registry.circuit_breakers[service_name]
    
    def _execute_request(self, endpoint: ServiceEndpoint, path: str, method: str,
                        headers: Dict[str, str] = None, data: Any = None,
                        params: Dict[str, str] = None, route_rule: RouteRule = None) -> Dict[str, Any]:
        """Execute request to endpoint"""
        url = f"{endpoint.url}{path}"
        request_headers = headers or {}
        request_params = params or {}
        
        # Add route rule headers and params
        if route_rule:
            request_headers.update(route_rule.headers)
            request_params.update(route_rule.query_params)
        
        # Track active connection
        endpoint.active_connections += 1
        start_time = time.time()
        
        try:
            # Make request
            if method.upper() == "GET":
                response = requests.get(
                    url, 
                    headers=request_headers, 
                    params=request_params,
                    timeout=route_rule.timeout if route_rule else 30
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url,
                    headers=request_headers,
                    params=request_params,
                    json=data,
                    timeout=route_rule.timeout if route_rule else 30
                )
            elif method.upper() == "PUT":
                response = requests.put(
                    url,
                    headers=request_headers,
                    params=request_params,
                    json=data,
                    timeout=route_rule.timeout if route_rule else 30
                )
            elif method.upper() == "DELETE":
                response = requests.delete(
                    url,
                    headers=request_headers,
                    params=request_params,
                    timeout=route_rule.timeout if route_rule else 30
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Update endpoint statistics
            success = response.status_code < 400
            self.service_registry.update_endpoint_stats(
                route_rule.service_name if route_rule else "unknown",
                endpoint.id,
                response_time_ms,
                success
            )
            
            # Record request history
            self._record_request(endpoint, path, method, response_time_ms, success)
            
            # Return response
            try:
                response_data = response.json()
            except:
                response_data = {"message": response.text}
            
            return {
                "status_code": response.status_code,
                "data": response_data,
                "response_time_ms": response_time_ms,
                "endpoint": endpoint.url
            }
            
        except requests.exceptions.RequestException as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            # Update endpoint statistics
            self.service_registry.update_endpoint_stats(
                route_rule.service_name if route_rule else "unknown",
                endpoint.id,
                response_time_ms,
                False
            )
            
            # Record failed request
            self._record_request(endpoint, path, method, response_time_ms, False)
            
            raise e
            
        finally:
            # Decrease active connections
            endpoint.active_connections = max(0, endpoint.active_connections - 1)
    
    def _record_request(self, endpoint: ServiceEndpoint, path: str, method: str,
                       response_time_ms: float, success: bool):
        """Record request for analytics"""
        request_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint_id": endpoint.id,
            "endpoint_url": endpoint.url,
            "path": path,
            "method": method,
            "response_time_ms": response_time_ms,
            "success": success
        }
        
        self.request_history.append(request_record)
        
        # Update performance metrics
        self.performance_metrics[endpoint.id].append({
            "timestamp": datetime.utcnow(),
            "response_time_ms": response_time_ms,
            "success": success
        })
    
    def get_service_status(self, service_name: str = None) -> Dict[str, Any]:
        """Get status of services"""
        if service_name:
            endpoints = self.service_registry.services.get(service_name, [])
            return {
                "service_name": service_name,
                "endpoints": [asdict(ep) for ep in endpoints],
                "healthy_count": len([ep for ep in endpoints if ep.is_healthy]),
                "total_count": len(endpoints)
            }
        else:
            status = {}
            for svc_name, endpoints in self.service_registry.services.items():
                status[svc_name] = {
                    "endpoints": [asdict(ep) for ep in endpoints],
                    "healthy_count": len([ep for ep in endpoints if ep.is_healthy]),
                    "total_count": len(endpoints)
                }
            return status
    
    def get_routing_metrics(self) -> Dict[str, Any]:
        """Get routing performance metrics"""
        total_requests = len(self.request_history)
        successful_requests = len([r for r in self.request_history if r["success"]])
        
        if total_requests == 0:
            return {
                "total_requests": 0,
                "success_rate": 0,
                "avg_response_time_ms": 0,
                "endpoint_metrics": {}
            }
        
        success_rate = (successful_requests / total_requests) * 100
        avg_response_time = sum(r["response_time_ms"] for r in self.request_history) / total_requests
        
        # Endpoint-specific metrics
        endpoint_metrics = {}
        for endpoint_id, metrics in self.performance_metrics.items():
            if metrics:
                endpoint_metrics[endpoint_id] = {
                    "total_requests": len(metrics),
                    "success_rate": (len([m for m in metrics if m["success"]]) / len(metrics)) * 100,
                    "avg_response_time_ms": sum(m["response_time_ms"] for m in metrics) / len(metrics),
                    "last_request": max(m["timestamp"] for m in metrics).isoformat()
                }
        
        return {
            "total_requests": total_requests,
            "success_rate": round(success_rate, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "endpoint_metrics": endpoint_metrics,
            "circuit_breaker_status": {
                name: cb.state for name, cb in self.service_registry.circuit_breakers.items()
            }
        }
    
    def add_service_endpoint(self, service_name: str, host: str, port: int,
                           weight: int = 1, protocol: str = "http") -> str:
        """Add a new service endpoint"""
        endpoint_id = f"{service_name}-{host}-{port}"
        endpoint = ServiceEndpoint(
            id=endpoint_id,
            host=host,
            port=port,
            protocol=protocol,
            weight=weight
        )
        
        self.service_registry.register_service(service_name, endpoint)
        return endpoint_id
    
    def remove_service_endpoint(self, service_name: str, endpoint_id: str):
        """Remove a service endpoint"""
        self.service_registry.unregister_service(service_name, endpoint_id)
    
    def update_endpoint_weight(self, service_name: str, endpoint_id: str, weight: int):
        """Update endpoint weight"""
        with self.service_registry.lock:
            for endpoint in self.service_registry.services.get(service_name, []):
                if endpoint.id == endpoint_id:
                    endpoint.weight = weight
                    logger.info(f"Updated weight for {endpoint_id} to {weight}")
                    break

# Global router instance
notification_router = NotificationRouter()

def route_notification_request(path: str, method: str = "POST",
                             headers: Dict[str, str] = None,
                             data: Any = None) -> Tuple[bool, Dict[str, Any]]:
    """Route a notification request"""
    return notification_router.route_request(path, method, headers, data)

def get_service_health() -> Dict[str, Any]:
    """Get health status of all services"""
    return notification_router.get_service_status()

def get_routing_performance() -> Dict[str, Any]:
    """Get routing performance metrics"""
    return notification_router.get_routing_metrics()

def register_notification_service(service_name: str, host: str, port: int,
                                 weight: int = 1) -> str:
    """Register a new notification service endpoint"""
    return notification_router.add_service_endpoint(service_name, host, port, weight)

def unregister_notification_service(service_name: str, endpoint_id: str):
    """Unregister a notification service endpoint"""
    notification_router.remove_service_endpoint(service_name, endpoint_id)
