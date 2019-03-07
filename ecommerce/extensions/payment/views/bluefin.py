import logging

from django.http import JsonResponse
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.forms import BluefinSubmitForm, PaymentForm
from ecommerce.extensions.payment.processors.bluefin import Bluefin
from ecommerce.extensions.payment.views import BasePaymentSubmitView

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class(
    'checkout.calculators', 'OrderTotalCalculator')


class BluefinSubmitView(EdxOrderPlacementMixin, BasePaymentSubmitView):
    """ Bluefin payment handler.

    The payment form should POST here. This view will handle Bluefin processing
    and redirection of the user to the receipt page.
    """

    form_class = BluefinSubmitForm

    @property
    def payment_processor(self):
        return Bluefin(self.request.site)

    def form_valid(self, form):
        form_data = form.cleaned_data
        basket = form_data['basket']
        order_number = basket.order_number

        basket_add_organization_attribute(basket, self.request.POST)

        try:
            billing_address = BillingAddress(
                first_name=form_data['first_name'],
                last_name=form_data['last_name'],
                line1=form_data['address_line1'],
                line2=form_data['address_line2'],
                line4=form_data['city'],  # Oscar uses line4 for city
                postcode=form_data['postal_code'],
                state=form_data['state'],
                country=Country.objects.get(
                    iso_3166_1_a2__iexact=form_data['country'])
            )

        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'An error occurred while parsing the billing address for \
                    basket [%d]. No billing address will be stored for \
                        the resulting order [%s].',
                basket.id,
                order_number)
            billing_address = None

        try:
            self.handle_payment(form_data, basket)
        except Exception:  # pylint: disable=broad-except
            logger.exception('An error occurred while processing the Bluefin \
                payment for basket [%d].', basket.id)
            return JsonResponse({}, status=400)

        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        order = self.handle_order_placement(
            order_number=order_number,
            user=basket.owner,
            basket=basket,
            shipping_address=None,
            shipping_method=shipping_method,
            shipping_charge=shipping_charge,
            billing_address=billing_address,
            order_total=order_total,
            request=self.request
        )
        self.handle_post_order(order)

        receipt_url = get_receipt_page_url(
            site_configuration=self.request.site.siteconfiguration,
            order_number=order_number
        )
        return JsonResponse({'url': receipt_url}, status=201)
