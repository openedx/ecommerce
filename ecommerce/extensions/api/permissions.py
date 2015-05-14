from rest_framework.permissions import BasePermission


class CanActForUser(BasePermission):
    """
    Allows access only if the user has permission to perform operations for the user represented by the username field
    in request.data.
    """

    def has_permission(self, request, view):
        username = request.data.get('username')

        if not username:
            return False

        user = request.user
        return user and (user.is_superuser or user.username == username)
