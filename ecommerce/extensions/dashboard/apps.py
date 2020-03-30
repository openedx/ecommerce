from __future__ import absolute_import

from django.apps import apps
from django.conf.urls import url
from oscar.apps.dashboard.apps import DashboardConfig as BaseDashboardConfig
from oscar.core.loading import get_class


class DashboardConfig(BaseDashboardConfig):
    name = 'ecommerce.extensions.dashboard'

    # pylint: disable=attribute-defined-outside-init, import-outside-toplevel
    def ready(self):
        super().ready()
        from auth_backends.urls import oauth2_urlpatterns
        from ecommerce.core.views import LogoutView
        # Note: Add ecommerce's logout override first to ensure it is registered by Django as the
        # actual logout view. Ecommerce's logout implementation supports different site configuration.
        self.AUTH_URLS = [url(r'^logout/$', LogoutView.as_view(), name='logout'), ] + oauth2_urlpatterns
        self.index_view = get_class('dashboard.views', 'ExtendedIndexView')
        self.refunds_app = apps.get_app_config('refunds_dashboard')

    def get_urls(self):
        urls = [
            url(r'^$', self.index_view.as_view(), name='index'),
            url(r'^catalogue/', self.catalogue_app.urls),
            url(r'^reports/', self.reports_app.urls),
            url(r'^orders/', self.orders_app.urls),
            url(r'^users/', self.users_app.urls),
            url(r'^pages/', self.pages_app.urls),
            url(r'^partners/', self.partners_app.urls),
            url(r'^offers/', self.offers_app.urls),
            url(r'^ranges/', self.ranges_app.urls),
            url(r'^reviews/', self.reviews_app.urls),
            url(r'^vouchers/', self.vouchers_app.urls),
            url(r'^comms/', self.comms_app.urls),
            url(r'^shipping/', self.shipping_app.urls),
            url(r'^refunds/', self.refunds_app.urls),
        ]
        urls += self.AUTH_URLS
        return self.post_process_urls(urls)
