from rest_framework import permissions


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
