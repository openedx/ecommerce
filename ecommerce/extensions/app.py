from oscar import app
from oscar.core.application import Application


class EdxShop(app.Shop):
    # URLs are only visible to users with staff permissions
    default_permissions = 'is_staff'

    # Override core app instances with blank application instances to exclude their URLs.
    promotions_app = Application()
    catalogue_app = Application()
    search_app = Application()


application = EdxShop()
