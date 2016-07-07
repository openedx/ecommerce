import json

from django.conf import settings
from django.http import JsonResponse
from django.views.generic import View
from waffle import flag_is_active
from waffle.models import Flag
from waffle.utils import get_setting as get_waffle_setting


class FeaturesList(View):
    """ Lists the current features in JSON, and writes them to a cookie. """

    def get(self, request):
        data = {'flags': {flag.name: flag_is_active(request, flag.name) for flag in Flag.objects.all()}}
        response = JsonResponse(data)
        response.set_cookie('features', json.dumps(data), max_age=get_waffle_setting('MAX_AGE'),
                            secure=get_waffle_setting('SECURE'), domain=settings.TOP_LEVEL_COOKIE_DOMAIN)
        return response
