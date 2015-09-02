from urlparse import urljoin


def get_lms_url(path):
    from django.conf import settings
    return urljoin(settings.LMS_URL_ROOT, path)
