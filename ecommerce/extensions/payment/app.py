import importlib

from oscar.core.application import Application

from ecommerce.extensions.payment.processors import BasePaymentProcessor


class PaymentApplication(Application):
    """Payment application class.

    This subclasses Oscar's base application class to create a custom
    container for Payment URLs and views
    """

    def get_urls(self):
        """Returns the URL patterns for the Payment Application."""
        urlpatterns = []
        for processor_class in BasePaymentProcessor.__subclasses__():
            urls_module_name = processor_class().URLS_MODULE
            if urls_module_name:
                urls_module = importlib.import_module(urls_module_name)
                module_urlpatterns = getattr(urls_module, 'urlpatterns')
                if module_urlpatterns:
                    urlpatterns.extend(module_urlpatterns)
        return self.post_process_urls(urlpatterns)


application = PaymentApplication()
