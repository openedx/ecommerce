from auth_backends.views import EdxOpenIdConnectLoginView
from oscar.apps.customer import app

from ecommerce.core.views import LogoutView


class CustomerApplication(app.CustomerApplication):
    login_view = EdxOpenIdConnectLoginView
    logout_view = LogoutView


application = CustomerApplication()
