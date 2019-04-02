import logging

import waffle
from django.conf import settings
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from rest_framework import permissions
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.enterprise.api import get_with_access_to
from ecommerce.enterprise.constants import USE_ROLE_BASED_ACCESS_CONTROL
from ecommerce.extensions.api.serializers import retrieve_enterprise_condition

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
        return (user.is_authenticated() and user.is_staff) or view.action == 'offers'


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


class HasDataAPIDjangoGroupAccess(permissions.BasePermission):
    """
    Permission that checks to see if the request user is part of the enterprise_data_api django group.

    Also checks that the user is authorized for the request's enterprise.
    """

    def get_enterprise_with_access_to(self, site, user, jwt, enterprise_id):
        """
        Get the enterprise customer data that the user has enterprise_data_api access to.

        Returns: enterprise or None if unable to get or user is not associated with an enterprise
        """
        try:
            enterprise_data = get_with_access_to(site, user, jwt, enterprise_id)
        except (ConnectionError, SlumberHttpBaseException, Timeout):
            LOGGER.exception('Failed to hit with_access_to endpoint for user [%s] and enterprise [%s]',
                             user, enterprise_id)
            return False
        if not enterprise_data:
            return False
        return enterprise_data

    def _request_is_permitted_for_enterprise(self, request, enterprise_id):
        token = request.auth or request.user.access_token
        permitted = self.get_enterprise_with_access_to(request.site, request.user, token, enterprise_id)
        if not permitted:
            LOGGER.warning('User %s denied access to Enterprise API for enterprise %s', request.user, enterprise_id)
        return permitted

    def has_permission(self, request, view):
        """
        Verify the user is staff or the associated enterprise matches the requested enterprise.
        """
        if waffle.switch_is_active(USE_ROLE_BASED_ACCESS_CONTROL):
            return True
        enterprise_id = request.parser_context.get('kwargs', {}).get('enterprise_id', '')
        if not enterprise_id:
            pk = request.parser_context.get('kwargs', {}).get('pk', '')
            try:
                coupon = Product.objects.get(pk=pk)
            except Product.DoesNotExist:
                return False
            enterprise_condition = retrieve_enterprise_condition(coupon)
            enterprise_id = enterprise_condition and enterprise_condition.enterprise_customer_uuid
        return self._request_is_permitted_for_enterprise(request, enterprise_id)


class CanReplaceUsername(permissions.BasePermission):
    """
    Grants access to the Username Replacement API for a the service user.
    """
    def has_permission(self, request, view):
        return request.user.username == getattr(settings, 'USERNAME_REPLACEMENT_WORKER')
