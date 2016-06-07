"""
Middleware for theming app

Note:
    This middleware depends on "django_sites_extensions.middleware.CurrentSiteWithDefaultMiddleware" middleware
    So it must be added after this middleware in django settings files.
"""

from ecommerce.theming.models import SiteTheme


class CurrentSiteThemeMiddleware(object):
    """
    Middleware that sets `site_theme` attribute to request object.
    """

    def process_request(self, request):
        request.site_theme = SiteTheme.get_theme(request.site)
