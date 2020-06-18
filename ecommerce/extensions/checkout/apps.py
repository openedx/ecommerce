

from django.conf.urls import url
from oscar.apps.checkout import apps
from oscar.core.loading import get_class


class CheckoutConfig(apps.CheckoutConfig):
    name = 'ecommerce.extensions.checkout'
    verbose_name = 'Checkout'

    # pylint: disable=attribute-defined-outside-init
    def ready(self):
        super().ready()

        # noinspection PyUnresolvedReferences
        import ecommerce.extensions.checkout.signals  # pylint: disable=unused-import, import-outside-toplevel
        self.free_checkout = get_class('checkout.views', 'FreeCheckoutView')
        self.cancel_checkout = get_class('checkout.views', 'CancelCheckoutView')
        self.checkout_error = get_class('checkout.views', 'CheckoutErrorView')
        self.receipt_response = get_class('checkout.views', 'ReceiptResponseView')

    def get_urls(self):
        urls = [
            url(r'^free-checkout/$', self.free_checkout.as_view(), name='free-checkout'),
            url(r'^cancel-checkout/$', self.cancel_checkout.as_view(), name='cancel-checkout'),
            url(r'^error/', self.checkout_error.as_view(), name='error'),
            url(r'^receipt/', self.receipt_response.as_view(), name='receipt'),

            url(r'^$', self.index_view.as_view(), name='index'),

            # Shipping/user address views
            url(r'shipping-address/$',
                self.shipping_address_view.as_view(), name='shipping-address'),
            url(r'user-address/edit/(?P<pk>\d+)/$',
                self.user_address_update_view.as_view(),
                name='user-address-update'),
            url(r'user-address/delete/(?P<pk>\d+)/$',
                self.user_address_delete_view.as_view(),
                name='user-address-delete'),

            # Shipping method views
            url(r'shipping-method/$',
                self.shipping_method_view.as_view(), name='shipping-method'),

            # Payment views
            url(r'payment-method/$',
                self.payment_method_view.as_view(), name='payment-method'),
            url(r'payment-details/$',
                self.payment_details_view.as_view(), name='payment-details'),

            # Preview
            url(r'preview/$',
                self.payment_details_view.as_view(preview=True),
                name='preview'),
        ]
        return self.post_process_urls(urls)
