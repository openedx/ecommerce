import logging

from requests.exceptions import ConnectionError, Timeout
from rest_framework import permissions

from slumber.exceptions import SlumberHttpBaseException

from ecommerce.enterprise.api import fetch_enterprise_learner_data, get_with_access_to


LOGGER = logging.getLogger(__name__)


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

    def get_enterprise_with_access_to(self, site, user, enterprise_id):
        """
        Get the enterprise customer data that the user has enterprise_data_api access to.

        Returns: enterprise or None if unable to get or user is not associated with an enterprise
        """
        enterprise_data = get_with_access_to(site, user, enterprise_id)
        if not enterprise_data:
            return None
        return enterprise_data

    def has_permission(self, request, view):
        """
        Verify the user is staff or the associated enterprise matches the requested enterprise.
        """
        enterprise_id = request.parser_context.get('kwargs', {}).get('enterprise_id', '')
        if not enterprise_id:
            try:
                learner_data = fetch_enterprise_learner_data(request.site, request.user)['results'][0]
                if learner_data and 'enterprise_customer' in learner_data:
                    enterprise_id = learner_data['enterprise_customer']['uuid']
            except (ConnectionError, KeyError, SlumberHttpBaseException, Timeout):
                LOGGER.exception(
                    'Failed to retrieve enterprise id for site [%s] and user [%s].', request.site, request.user)
                return False
        permitted = self.get_enterprise_with_access_to(request.site, request.user, enterprise_id)
        if not permitted:
            LOGGER.warning('User %s denied access to Enterprise API for enterprise %s', request.user, enterprise_id)
        return permitted
