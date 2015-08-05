from django.conf import settings


def core(_request):
    return {
        'platform_name': settings.PLATFORM_NAME
    }
