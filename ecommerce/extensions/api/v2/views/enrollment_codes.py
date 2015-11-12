from decimal import Decimal
import dateutil.parser
import logging

from django.db import transaction
from oscar.core.loading import get_model
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ecommerce.extensions.api import serializers, data as data_api
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.catalogue.utils import generate_sku
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.helpers import get_processor_class_by_name
from ecommerce.extensions.payment.processors.invoice import InvoicePayment

AttributeOption = get_model('catalogue', 'AttributeOption')
Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
Client = get_model('core', 'Client')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


class EnrollmentCodeOrderCreateView(generics.CreateAPIView, EdxOrderPlacementMixin):
    serializer_class = serializers.EnrollmentCodeOrderSerializer
    permission_classes = (IsAuthenticated, IsAdminUser)

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            client = request.data[AC.KEYS.CLIENT]
            stock_records = request.data[AC.KEYS.STOCK_RECORDS]
            start_date = dateutil.parser.parse(request.data[AC.KEYS.START_DATE])
            end_date = dateutil.parser.parse(request.data[AC.KEYS.END_DATE])
            ecode_type = request.data[AC.KEYS.TYPE]
            quantity = request.data[AC.KEYS.QUANTITY]
            price = request.data[AC.KEYS.PRICE]
            partner = request.site.siteconfiguration.partner

            enrollment_code_product = self._create_enrollment_code_product(
                client, stock_records, start_date,
                end_date, ecode_type, price, partner
            )

            self._add_product_to_basket(
                product=enrollment_code_product,
                user=request.user,
                site=request.site,
                quantity=quantity
            )

            basket = Basket.get_basket(request.user, request.site)
            order_metadata = data_api.get_order_metadata(basket)
            self._create_order(basket, order_metadata)

            ### RESPONSE ###
            response_data = {
                AC.KEYS.BASKET_ID: basket.id,
                AC.KEYS.ORDER: None,
                AC.KEYS.PAYMENT_DATA: None,
            }

            return Response(response_data, status=status.HTTP_200_OK)

    def _create_enrollment_code_product(self, client, stock_records, start_date,
                                        end_date, ecode_type, price, partner):
        ### ENROLLMENT PRODUCT ###
        enrollment_code_client, created = Client.objects.get_or_create(username=client)
        enrollment_code_catalog = Catalog.objects.create(
            name='Enrollment Code',
            partner_id=partner.id
        )
        product_class = ProductClass.objects.get(slug='enrollment_code')

        for stock_record_id in stock_records:
            enrollment_code_catalog.stock_records.add(
                StockRecord.objects.get(id=stock_record_id)
            )

        enrollment_code_product = Product()
        enrollment_code_product.product_class = product_class
        enrollment_code_product.title = '-'.join((
            enrollment_code_client.username,
            unicode(enrollment_code_catalog)
        ))

        enrollment_code_type = AttributeOption.objects.get(
            option=ecode_type
        )

        enrollment_code_product.attr.catalog = enrollment_code_catalog
        enrollment_code_product.attr.client = enrollment_code_client
        enrollment_code_product.attr.start_date = start_date
        enrollment_code_product.attr.end_date = end_date
        enrollment_code_product.attr.type = enrollment_code_type

        # Product validation
        try:
            enrollment_code_product.clean()
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(
                'Failed to create product for Enrollment Code [%d]. Basket has been thawed.',
                enrollment_code_product.title
            )
            return Response({'developer_message': ex.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        enrollment_code_product.save()

        ### STOCK RECORD ###
        sku = generate_sku(enrollment_code_product, partner)

        stock_record = StockRecord(
            product=enrollment_code_product,
            partner=partner,
            partner_sku=sku
        )
        stock_record.price_currency = 'USD'
        stock_record.price_excl_tax = price
        stock_record.save()

        return enrollment_code_product

    def _add_product_to_basket(self, product, user, site, quantity):

        basket = Basket.get_basket(user, site)
        basket.add_product(product, quantity=quantity)
        logger.info(
            u"Added product with SKU [%s] to basket [%d]",
            product.stockrecords.first().partner_sku, basket.id
        )
        return basket

    def _create_order(self, basket, order_metadata, payment_process_name='invoice'):
        basket.freeze()

        order = self.handle_order_placement(
            order_number=order_metadata[AC.KEYS.ORDER_NUMBER],
            user=basket.owner,
            basket=basket,
            shipping_address=None,
            shipping_method=order_metadata[AC.KEYS.SHIPPING_METHOD],
            shipping_charge=order_metadata[AC.KEYS.SHIPPING_CHARGE],
            billing_address=None,
            order_total=order_metadata[AC.KEYS.ORDER_TOTAL],
        )

        logger.info(
            u"Created new order number [%s] from basket [%d]",
            order_metadata[AC.KEYS.ORDER_NUMBER],
            basket.id
        )

        if payment_process_name == 'invoice':
            fake_response = {
                'req_currency': order_metadata['total'].currency,
                'req_amount': Decimal(order_metadata[AC.KEYS.ORDER_TOTAL].excl_tax),
                'transaction_id': -1
            }
            payment_processor = InvoicePayment
            payment_processor().handle_processor_response(response=fake_response, basket=basket)
        else:
            payment_processor = get_processor_class_by_name(payment_process_name)
            parameters = payment_processor().get_transaction_parameters(basket, request=self.request)

        return order
