from django.conf.urls import url, include
from oscar import app


class EdxShop(app.Shop):
    # URLs are only visible to users with staff permissions
    default_permissions = 'is_staff'

    def get_urls(self):
        urls = [
            # Make management dashboard accessible at the root
            url(r'', include(self.dashboard_app.urls)),
            url(r'^promotions/', include(self.promotions_app.urls)),
            url(r'^catalogue/', include(self.catalogue_app.urls)),
            url(r'^basket/', include(self.basket_app.urls)),
            url(r'^checkout/', include(self.checkout_app.urls)),
            url(r'^accounts/', include(self.customer_app.urls)),
            url(r'^search/', include(self.search_app.urls)),
            url(r'^offers/', include(self.offer_app.urls)),
        ]
        return urls


application = EdxShop()
