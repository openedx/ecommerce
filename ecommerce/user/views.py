import uuid

from django.conf import settings
from django.contrib.auth import get_user_model, login, authenticate
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import View


User = get_user_model()


class AutoAuth(View):
    """Creates and authenticates a new User with superuser permissions.

    If the ENABLE_AUTO_AUTH setting is not True, returns a 404.
    """
    def get(self, request):
        if not getattr(settings, 'ENABLE_AUTO_AUTH', None):
            raise Http404

        if not getattr(settings, 'AUTO_AUTH_USERNAME_PREFIX', None):
            raise ValueError('AUTO_AUTH_USERNAME_PREFIX must be set.')

        # Create a new user with staff permissions
        username = password = settings.AUTO_AUTH_USERNAME_PREFIX + uuid.uuid4().hex[0:20]
        User.objects.create_superuser(username, email=None, password=password)

        # Log in the new user
        user = authenticate(username=username, password=password)
        login(request, user)

        return redirect('/')
