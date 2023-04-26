"""
Permission classes for Product Entitlement Information API
"""
from django.conf import settings
from rest_framework import permissions


class CanGetProductEntitlementInfo(permissions.BasePermission):
    """
    Grant access to the product entitlement API for the service user or superusers.
    """

    def has_permission(self, request, view):
        return request.user.is_superuser or request.user.is_staff or (
            request.user.username == settings.SUBSCRIPTIONS_SERVICE_WORKER_USERNAME)
