from django.conf import settings

from ecommerce.core.url_utils import get_lms_dashboard_url


def core(_request):
    return {
        'lms_dashboard_url': get_lms_dashboard_url(),
        'platform_name': _request.site.name,
        'support_url': settings.SUPPORT_URL,
    }
