from django.conf import settings


def core(_request):
    return {
        'support_url': settings.SUPPORT_URL,
        'platform_name': settings.PLATFORM_NAME
    }
