from auth_backends.urls import auth_urlpatterns
from django.conf.urls import include, url
from oscar.apps.dashboard import app
from oscar.core.loading import get_class

from ecommerce.core.views import LogoutView

# NOTE: This should match AUTH_URLS in ecommerce/urls.py. These are duplicated here because Oscar's
# dashboard templates, strangely, reference dashboard:login and dashboard:logout instead of login and logout.
AUTH_URLS = [url(r'^logout/$', LogoutView.as_view(), name='logout'), ] + auth_urlpatterns


class DashboardApplication(app.DashboardApplication):
    index_view = get_class('dashboard.views', 'ExtendedIndexView')
    refunds_app = get_class('dashboard.refunds.app', 'application')

    def get_urls(self):
        urls = [
            url(r'^$', self.index_view.as_view(), name='index'),
            url(r'^catalogue/', include(self.catalogue_app.urls)),
            url(r'^reports/', include(self.reports_app.urls)),
            url(r'^orders/', include(self.orders_app.urls)),
            url(r'^users/', include(self.users_app.urls)),
            url(r'^content-blocks/', include(self.promotions_app.urls)),
            url(r'^pages/', include(self.pages_app.urls)),
            url(r'^partners/', include(self.partners_app.urls)),
            url(r'^offers/', include(self.offers_app.urls)),
            url(r'^ranges/', include(self.ranges_app.urls)),
            url(r'^reviews/', include(self.reviews_app.urls)),
            url(r'^vouchers/', include(self.vouchers_app.urls)),
            url(r'^comms/', include(self.comms_app.urls)),
            url(r'^shipping/', include(self.shipping_app.urls)),
            url(r'^refunds/', include(self.refunds_app.urls)),
        ]
        urls += AUTH_URLS
        return self.post_process_urls(urls)


application = DashboardApplication()
