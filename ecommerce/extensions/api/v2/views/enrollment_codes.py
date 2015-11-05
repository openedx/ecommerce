import logging

from django.db import transaction
from django.utils.decorators import method_decorator
from oscar.core.loading import get_class, get_model
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.api import serializers, data as data_api
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin


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
            start_date = request.data[AC.KEYS.START_DATE]
            end_date = request.data[AC.KEYS.END_DATE]
            quantity = request.data[AC.KEYS.QUANTITY]
            basket = Basket.get_basket(request.user, request.site)

            ### ENROLLMENT PRODUCT ###
            enrollment_code_client = Client.objects.get_or_create(
                username=client
            )
            partner = request.site.siteconfiguration.partner
            enrollment_code_catalog = Catalog.objects.create(
                partner_id=partner.id
            )
            product_class = ProductClass.objects.get(slug='enrollment_code')

            # TODO: calculate and assign the proper price
            price = 0
            for id in stock_records:
                enrollment_code_catalog.stock_records.add(
                    StockRecord.objects.get(id=id)
                )
                price += 10

            enrollment_code_product = Product.objects.create(
                product_class=product_class,
                title='replace-me'
            )

            enrollment_code_product.attr.catalog = enrollment_code_catalog
            enrollment_code_product.attr.client = enrollment_code_client
            enrollment_code_product.attr.start_date = start_date
            enrollment_code_product.attr.end_date = end_date

            ### STOCK RECORD ###
            sku = 'replace-me3'

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
            basket.add_product(enrollment_code_product)
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
            # # TODO:
            # # create order (_checkout)