

from oscar.apps.customer import apps


class CustomerConfig(apps.CustomerConfig):
    name = 'ecommerce.extensions.customer'

    # pylint: disable=attribute-defined-outside-init, import-outside-toplevel
    def ready(self):
        super().ready()
        from auth_backends.views import EdxOAuth2LoginView
        from ecommerce.core.views import LogoutView
        self.login_view = EdxOAuth2LoginView
        self.logout_view = LogoutView
