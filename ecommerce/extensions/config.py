

from django.conf import settings
from django.conf.urls import url
from django.views.generic import RedirectView
from oscar import config

from .utils import exclude_app_urls


class EdxShop(config.Shop):
    name = "ecommerce"
    # URLs are only visible to users with staff permissions
    default_permissions = 'is_staff'

    def get_urls(self):
        urls = [
            url(r'^$', RedirectView.as_view(url=settings.OSCAR_HOMEPAGE), name='home'),
        ] + super().get_urls()
        # excluding urls of catalogue and search
        exclude_app_urls(urls, 'catalogue')
        exclude_app_urls(urls, 'search')
        return urls
