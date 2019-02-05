from auth_backends.views import EdxOAuth2LoginView
from oscar.apps.customer import app

from ecommerce.core.views import LogoutView


class CustomerApplication(app.CustomerApplication):
    login_view = EdxOAuth2LoginView
    logout_view = LogoutView


application = CustomerApplication()
