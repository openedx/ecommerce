"""Throttles for rate-limiting requests to API endpoints."""
from django.conf import settings
from rest_framework.throttling import UserRateThrottle


class OrdersThrottle(UserRateThrottle):
    """Limit the number of requests users can make to the orders endpoint."""
    rate = getattr(settings, 'ORDERS_ENDPOINT_RATE_LIMIT', '40/minute')
