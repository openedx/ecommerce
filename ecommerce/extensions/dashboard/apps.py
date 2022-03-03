

from django.apps import apps
from django.urls import include, path
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
        self.AUTH_URLS = [path('logout/', LogoutView.as_view(), name='logout'), ] + oauth2_urlpatterns
        self.index_view = get_class('dashboard.views', 'ExtendedIndexView')
        self.refunds_app = apps.get_app_config('refunds_dashboard')

    def get_urls(self):
        urls = [
            path('', self.index_view.as_view(), name='index'),
            path('catalogue/', include(self.catalogue_app.urls[0])),
            path('reports/', include(self.reports_app.urls[0])),
            path('orders/', include(self.orders_app.urls[0])),
            path('users/', include(self.users_app.urls[0])),
            path('pages/', include(self.pages_app.urls[0])),
            path('partners/', include(self.partners_app.urls[0])),
            path('offers/', include(self.offers_app.urls[0])),
            path('ranges/', include(self.ranges_app.urls[0])),
            path('reviews/', include(self.reviews_app.urls[0])),
            path('vouchers/', include(self.vouchers_app.urls[0])),
            path('comms/', include(self.comms_app.urls[0])),
            path('shipping/', include(self.shipping_app.urls[0])),
            path('refunds/', include(self.refunds_app.urls[0])),
        ]
        urls += self.AUTH_URLS
        return self.post_process_urls(urls)
