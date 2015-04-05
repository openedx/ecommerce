from oscar.core.application import Application

from ecommerce.extensions.api.urls import urlpatterns


class ApiApplication(Application):
    """API application class.

    This subclasses Oscar's base application class to create a custom
    container for the API's URLs, views, and permissions.
    """
    def get_urls(self):
        """Returns the URL patterns for the API."""
        return self.post_process_urls(urlpatterns)


application = ApiApplication()
