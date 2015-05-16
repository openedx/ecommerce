from oscar import app


class EdxShop(app.Shop):
    # URLs are only visible to users with staff permissions
    default_permissions = 'is_staff'


application = EdxShop()
