from django.conf import settings


def get_settings(request):
    return {
        'username': request.user.username if not request.user.is_anonymous() else None,
        'lms_dashboard_url': settings.LMS_DASHBOARD_URL
    }
