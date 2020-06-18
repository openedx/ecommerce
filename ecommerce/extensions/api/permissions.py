

import logging

from django.conf import settings
from oscar.core.loading import get_model
from rest_framework import permissions

Product = get_model('catalogue', 'Product')

LOGGER = logging.getLogger(__name__)

USERNAME_REPLACEMENT_GROUP = "username_replacement_admin"


class CanActForUser(permissions.IsAdminUser):
    """
    Allows access only if the user has permission to perform operations for the user represented by the username field
    in request.data.
    """

    def has_permission(self, request, view):
        user = request.user
        username = request.data.get('username')

        if not username:
            return False

        return super(CanActForUser, self).has_permission(request, view) or (user and user.username == username)


class IsOffersOrIsAuthenticatedAndStaff(permissions.BasePermission):
    """ Permission that allows access to anonymous users to get course offers. """

    def has_permission(self, request, view):
        user = request.user
        # pylint: disable=consider-using-ternary
        return (user.is_authenticated and user.is_staff) or view.action == 'offers'


class IsStaffOrOwner(permissions.BasePermission):
    """
    Permission that allows access to admin users or the owner of an object.
    The owner is considered the User object represented by obj.user.
    """

    def has_object_permission(self, request, view, obj):
        return request.user and (request.user.is_staff or obj.user == request.user)


class IsStaffOrModelPermissionsOrAnonReadOnly(permissions.DjangoModelPermissionsOrAnonReadOnly):
    """
    Permission that allows staff users and users that have been granted specific access to write,
    but allows read access to anyone.
    """
    def has_permission(self, request, view):
        user = request.user
        return user.is_staff or super(IsStaffOrModelPermissionsOrAnonReadOnly, self).has_permission(request, view)


class CanReplaceUsername(permissions.BasePermission):
    """
    Grants access to the Username Replacement API for a the service user.
    """
    def has_permission(self, request, view):
        return request.user.username == getattr(settings, 'USERNAME_REPLACEMENT_WORKER')
