import logging

from django.contrib.auth import get_user_model
from oscar.core.loading import get_model
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ecommerce.bff.subscriptions.permissions import CanGetProductEntitlementInfo
from ecommerce.bff.subscriptions.serializers import CourseEntitlementInfoSerializer
from ecommerce.extensions.api.exceptions import BadRequestException
from ecommerce.extensions.api.throttles import ServiceUserThrottle
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.utils import embargo_check

logger = logging.getLogger(__name__)

Product = get_model('catalogue', 'Product')
User = get_user_model()


class ProductEntitlementInfoView(generics.GenericAPIView):

    serializer_class = CourseEntitlementInfoSerializer
    permission_classes = (IsAuthenticated, CanGetProductEntitlementInfo)
    throttle_classes = [ServiceUserThrottle]

    def post(self, request, *args, **kwargs):
        try:
            skus = request.POST.getlist('skus', [])
            username = request.POST.get('username', None)
            site = request.site
            user_ip_address = request.POST.get('user_ip_address', None)

            products = self._get_products_by_skus(skus)
            available_products = self._get_available_products(products)
            data = []
            if request.site.siteconfiguration.enable_embargo_check:
                if not embargo_check(username, site, available_products, user_ip_address):
                    logger.error(
                        'B2C_SUBSCRIPTIONS: User [%s] blocked by embargo, not continuing with the checkout process.',
                        username
                    )
                    return Response({'error': 'User blocked by embargo check',
                                     'error_code': 'embargo_failed'},
                                    status=status.HTTP_200_OK)

            for product in available_products:
                mode = self._mode_for_product(product)
                if hasattr(product.attr, 'UUID') and mode is not None:
                    data.append({'course_uuid': product.attr.UUID, 'mode': mode,
                                 'sku': product.stockrecords.first().partner_sku})
                else:
                    logger.error(f"B2C_SUBSCRIPTIONS: Product {product}"
                                 " does not have a UUID attribute or mode is None")
            return Response({'data': data})
        except BadRequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _get_available_products(self, products):
        unavailable_product_ids = []
        for product in products:
            purchase_info = self.request.strategy.fetch_for_product(product)
            if not purchase_info.availability.is_available_to_buy:
                logger.warning('B2C_SUBSCRIPTIONS: Product [%s] is not available to buy.', product.title)
                unavailable_product_ids.append(product.id)

        available_products = products.exclude(id__in=unavailable_product_ids)
        if not available_products:
            raise BadRequestException('No product is available to buy.')
        return available_products

    def _get_products_by_skus(self, skus):
        if not skus:
            raise BadRequestException(('No SKUs provided.'))

        partner = get_partner_for_site(self.request)
        products = Product.objects.filter(stockrecords__partner=partner, stockrecords__partner_sku__in=skus)
        if not products:
            raise BadRequestException(('Products with SKU(s) [{skus}] do not exist.').format(skus=', '.join(skus)))
        return products

    def _mode_for_product(self, product):
        """
        Returns the purchaseable enrollment mode (aka course mode) for the specified product.
        If a purchaseable enrollment mode cannot be determined, None is returned.

        """
        mode = getattr(product.attr, 'certificate_type', getattr(product.attr, 'seat_type', None))
        if not mode:
            return None
        if mode == 'professional' and not getattr(product.attr, 'id_verification_required', False):
            return 'no-id-professional'
        return mode
