from oscar.core.application import Application

from ecommerce.extensions.payment.urls import urlpatterns


class PaymentApplication(Application):
    """Payment application class.

    This subclasses Oscar's base application class to create a custom
    container for Payment URLs and views
    """

    def get_urls(self):
        """Returns the URL patterns for the Payment Application."""
        return self.post_process_urls(urlpatterns)


application = PaymentApplication()
