import dateutil.parser
import logging

from django.db import transaction
from oscar.core.loading import get_model
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.api import serializers, data as data_api
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.catalogue.utils import generate_sku
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin

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
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            client = request.data[AC.KEYS.CLIENT]
            stock_records = request.data[AC.KEYS.STOCK_RECORDS]
            # Needs to be casted to a date object.
            start_date = dateutil.parser.parse(request.data[AC.KEYS.START_DATE])
            end_date = dateutil.parser.parse(request.data[AC.KEYS.END_DATE])
            type = request.data[AC.KEYS.TYPE]
            quantity = request.data[AC.KEYS.QUANTITY]
            price = request.data[AC.KEYS.PRICE]


            ### ENROLLMENT PRODUCT ###
            enrollment_code_client, created = Client.objects.get_or_create(
                username=client,
                # TODO: implement 'short_code' field to Client model?
                #       short_code=client.lower().replace(' ', '_')
            )
            partner = request.site.siteconfiguration.partner
            enrollment_code_catalog = Catalog.objects.create(
                name='Enrollment Code',
                partner_id=partner.id
            )
            product_class = ProductClass.objects.get(slug='enrollment_code')

            for stock_record_id in stock_records:
                enrollment_code_catalog.stock_records.add(
                    StockRecord.objects.get(id=stock_record_id)
                )

            enrollment_code_product = Product.objects.create(
                product_class=product_class,
                title='-'.join((
                    enrollment_code_client.username,
                    unicode(enrollment_code_catalog)
                ))
            )

            enrollment_code_type = AttributeOption.objects.get(
                option=type
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


            ### BASKET ###
            basket = Basket.get_basket(request.user, request.site)
            basket.add_product(enrollment_code_product, quantity=quantity)
            logger.info(u"Added product with SKU [%s] to basket [%d]", sku, basket.id)


            ### ORDER ###
            basket.freeze()
            order_metadata = data_api.get_order_metadata(basket)
            pricing = order_metadata[AC.KEYS.ORDER_TOTAL]
            Order.objects.create(
                number=order_metadata[AC.KEYS.ORDER_NUMBER],
                basket=basket,
                currency=pricing.currency,
                total_incl_tax=pricing.incl_tax,
                total_excl_tax=pricing.excl_tax
            )
            basket.submit()

            logger.info(
                u"Created new order number [%s] from basket [%d]",
                order_metadata[AC.KEYS.ORDER_NUMBER],
                basket.id
            )


            ### RESPONSE ###
            response_data = {
                AC.KEYS.BASKET_ID: basket.id,
                AC.KEYS.ORDER: None,
                AC.KEYS.PAYMENT_DATA: None,
            }

            return Response(response_data, status=status.HTTP_200_OK)
