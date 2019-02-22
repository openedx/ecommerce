from __future__ import unicode_literals

import logging

import waffle
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from edx_rest_framework_extensions.paginators import DefaultPagination
from oscar.core.loading import get_model
from rest_framework import generics, serializers, status
from rest_framework.decorators import detail_route, list_route
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH
from ecommerce.enterprise.utils import get_enterprise_customers
from ecommerce.extensions.api.serializers import (
    CouponCodeAssignmentSerializer,
    CouponCodeRemindSerializer,
    CouponCodeRevokeSerializer,
    CouponSerializer,
    EnterpriseCouponListSerializer,
    EnterpriseCouponOverviewListSerializer,
    NotAssignedCodeUsageSerializer,
    NotRedeemedCodeUsageSerializer,
    PartialRedeemedCodeUsageSerializer,
    RedeemedCodeUsageSerializer
)
from ecommerce.extensions.api.v2.utils import send_new_codes_notification_email
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.catalogue.utils import (
    attach_vouchers_to_coupon_product,
    create_coupon_product_and_stockrecord
)
from ecommerce.extensions.offer.constants import (
    OFFER_ASSIGNED,
    OFFER_ASSIGNMENT_EMAIL_PENDING,
    VOUCHER_NOT_ASSIGNED,
    VOUCHER_NOT_REDEEMED,
    VOUCHER_PARTIAL_REDEEMED,
    VOUCHER_REDEEMED
)
from ecommerce.extensions.voucher.utils import (
    create_enterprise_vouchers,
    update_voucher_offer,
    update_voucher_with_enterprise_offer
)
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Line = get_model('basket', 'Line')
OfferAssignment = get_model('offer', 'OfferAssignment')
Product = get_model('catalogue', 'Product')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')

DEPRECATED_COUPON_CATEGORIES = ['Bulk Enrollment']


class EnterpriseCustomerViewSet(generics.GenericAPIView):

    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get(self, request):
        site = request.site
        return Response(data={'results': get_enterprise_customers(site)})


class EnterpriseCouponViewSet(CouponViewSet):
    """ Coupon resource. """
    pagination_class = DefaultPagination

    def get_queryset(self):
        enterprise_id = self.kwargs.get('enterprise_id')
        if enterprise_id:
            invoices = Invoice.objects.filter(business_client__enterprise_customer_uuid=enterprise_id)
        else:
            invoices = Invoice.objects.filter(business_client__enterprise_customer_uuid__isnull=False)
        orders = Order.objects.filter(id__in=[invoice.order_id for invoice in invoices])
        basket_lines = Line.objects.filter(basket_id__in=[order.basket_id for order in orders])
        return Product.objects.filter(
            product_class__name=COUPON_PRODUCT_CLASS_NAME,
            stockrecords__partner=self.request.site.siteconfiguration.partner,
            id__in=[line.product_id for line in basket_lines],
            coupon_vouchers__vouchers__offers__condition__enterprise_customer_uuid__isnull=False,
        ).distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return EnterpriseCouponListSerializer
        elif self.action == 'overview':
            return EnterpriseCouponOverviewListSerializer
        return CouponSerializer

    def validate_access_for_enterprise_switch(self, request_data):
        if not waffle.switch_is_active(ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH):
            raise ValidationError('This endpoint will be available once the enterprise offers switch is on.')

    @staticmethod
    def send_codes_availability_email(site, email_address, enterprise_id, coupon_id):
        send_new_codes_notification_email(site, email_address, enterprise_id, coupon_id)

    def create_coupon_and_vouchers(self, cleaned_voucher_data):
        coupon_product = create_coupon_product_and_stockrecord(
            cleaned_voucher_data['title'],
            cleaned_voucher_data['category'],
            cleaned_voucher_data['partner'],
            cleaned_voucher_data['price']
        )

        vouchers = create_enterprise_vouchers(
            voucher_type=cleaned_voucher_data['voucher_type'],
            quantity=cleaned_voucher_data['quantity'],
            coupon_id=coupon_product.id,
            benefit_type=cleaned_voucher_data['benefit_type'],
            benefit_value=cleaned_voucher_data['benefit_value'],
            enterprise_customer=cleaned_voucher_data['enterprise_customer'],
            enterprise_customer_catalog=cleaned_voucher_data['enterprise_customer_catalog'],
            max_uses=cleaned_voucher_data['max_uses'],
            email_domains=cleaned_voucher_data['email_domains'],
            site=self.request.site,
            end_datetime=cleaned_voucher_data['end_datetime'],
            start_datetime=cleaned_voucher_data['start_datetime'],
            code=cleaned_voucher_data['code'],
            name=cleaned_voucher_data['title']
        )

        attach_vouchers_to_coupon_product(
            coupon_product,
            vouchers,
            cleaned_voucher_data['note'],
            cleaned_voucher_data.get('notify_email')
        )
        return coupon_product

    def update(self, request, *args, **kwargs):
        """Update coupon depending on request data sent."""
        try:
            self.validate_access_for_enterprise_switch(request.data)
        except ValidationError as error:
            logger.exception(error.message)
            raise serializers.ValidationError(error.message)
        return super(EnterpriseCouponViewSet, self).update(request, *args, **kwargs)

    def update_range_data(self, request_data, vouchers):
        # Since enterprise coupons do not have ranges, we bypass the range update logic entirely.
        pass

    def update_offer_data(self, request_data, vouchers, site):
        """
        Remove all offers from the vouchers and add a new offer
        Arguments:
            request_data (dict): the request parameters sent via api.
            vouchers (list): the vouchers attached to this coupon to update.
            site (Site): the site for this request.
        """
        benefit_value = request_data.get('benefit_value')
        enterprise_customer = request_data.get('enterprise_customer', {}).get('id', None)
        enterprise_catalog = request_data.get('enterprise_customer_catalog') or None
        max_uses = request_data.get('max_uses')
        email_domains = request_data.get('email_domains')

        # Validate max_uses
        if max_uses is not None:
            if vouchers.first().usage == Voucher.SINGLE_USE:
                log_message_and_raise_validation_error(
                    'Failed to update Coupon. '
                    'max_global_applications field cannot be set for voucher type [{voucher_type}].'.format(
                        voucher_type=Voucher.SINGLE_USE
                    ))
            try:
                max_uses = int(max_uses)
                if max_uses < 1:
                    raise ValueError
            except ValueError:
                raise ValidationError('max_global_applications field must be a positive number.')

        coupon_was_migrated = False
        for voucher in vouchers.all():
            updated_enterprise_offer = update_voucher_with_enterprise_offer(
                offer=voucher.enterprise_offer,
                benefit_value=benefit_value,
                max_uses=max_uses,
                enterprise_customer=enterprise_customer,
                enterprise_catalog=enterprise_catalog,
                email_domains=email_domains,
                site=site,
            )
            updated_orginal_offer = None
            if voucher.original_offer != voucher.enterprise_offer:
                coupon_was_migrated = True
                updated_orginal_offer = update_voucher_offer(
                    offer=voucher.original_offer,
                    benefit_value=benefit_value,
                    max_uses=max_uses,
                    email_domains=email_domains,
                    site=site,
                )
            voucher.offers.clear()
            voucher.offers.add(updated_enterprise_offer)
            if updated_orginal_offer:
                voucher.offers.add(updated_orginal_offer)

        if coupon_was_migrated:
            super(EnterpriseCouponViewSet, self).update_range_data(request_data, vouchers)

    @detail_route(url_path='codes')
    def codes(self, request, pk, format=None):  # pylint: disable=unused-argument, redefined-builtin
        """
        GET codes belong to a `coupon`.

        Response will looks like
        {
            results: [
                {
                    code: '1234-5678-90',
                    assigned_to: 'Barry Allen',
                    redemptions: {
                        used: 1,
                        total: 5,
                    },
                    redeem_url: 'https://testserver.fake/coupons/offer/?code=1234-5678-90',
                },
            ]
        }
        """
        coupon = self.get_object()
        coupon_vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        usage_type = coupon_vouchers.first().usage
        code_filter = request.query_params.get('code_filter')
        queryset = None
        serializer_class = None

        if not code_filter:
            raise serializers.ValidationError('code_filter must be specified')

        if code_filter == VOUCHER_NOT_ASSIGNED:
            queryset = self._get_not_assigned_usages(coupon_vouchers)
            serializer_class = NotAssignedCodeUsageSerializer
        elif code_filter == VOUCHER_NOT_REDEEMED:
            queryset = self._get_not_redeemed_usages(coupon_vouchers)
            serializer_class = NotRedeemedCodeUsageSerializer
        elif code_filter == VOUCHER_PARTIAL_REDEEMED:
            queryset = self._get_partial_redeemed_usages(coupon_vouchers)
            serializer_class = PartialRedeemedCodeUsageSerializer
        elif code_filter == VOUCHER_REDEEMED:
            queryset = self._get_redeemed_usages(coupon_vouchers)
            serializer_class = RedeemedCodeUsageSerializer

        if not serializer_class:
            raise serializers.ValidationError('Invalid code_filter specified: {}'.format(code_filter))

        if format is None:
            page = self.paginate_queryset(queryset)
            serializer = serializer_class(page, many=True, context={'usage_type': usage_type})
            return self.get_paginated_response(serializer.data)

        serializer = serializer_class(queryset, many=True, context={'usage_type': usage_type})
        return Response(serializer.data)

    def _get_not_assigned_usages(self, vouchers):
        """
        Returns a queryset containing Vouchers with slots that have not been assigned.
        Unique Vouchers will be included in the final queryset for all types.
        """
        vouchers_with_slots = []
        for voucher in vouchers:
            slots_available = voucher.slots_available_for_assignment
            if slots_available == 0:
                continue

            vouchers_with_slots.append(voucher.id)

        return Voucher.objects.filter(id__in=vouchers_with_slots).values('code').order_by('code')

    def _get_not_redeemed_usages(self, vouchers):
        """
        Returns a queryset containing unique code and user_email pairs from OfferAssignments.
        Only code and user_email pairs that have no corresponding VoucherApplication are returned.
        """
        unredeemed_assignments = []
        for voucher in vouchers:
            users_having_usages = VoucherApplication.objects.filter(
                voucher=voucher).values_list('user__email', flat=True)

            assignments = voucher.enterprise_offer.offerassignment_set.filter(
                code=voucher.code,
                status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING]
            ).exclude(user_email__in=users_having_usages)

            if assignments.count() == 0:
                continue

            unredeemed_assignments.append(assignments.first().id)

        return OfferAssignment.objects.filter(
            id__in=unredeemed_assignments).values('code', 'user_email').order_by('user_email')

    def _get_partial_redeemed_usages(self, vouchers):
        """
        Returns a queryset containing unique code and user_email pairs from OfferAssignments.
        Only code and user_email pairs that have at least one corresponding VoucherApplication are returned.
        """
        # There are no partially redeemed SINGLE_USE codes, so return the empty queryset.
        if vouchers.first().usage == Voucher.SINGLE_USE:
            return OfferAssignment.objects.none()

        parially_redeemed_assignments = []
        for voucher in vouchers:
            users_having_usages = VoucherApplication.objects.filter(
                voucher=voucher).values_list('user__email', flat=True)

            assignments = voucher.enterprise_offer.offerassignment_set.filter(
                code=voucher.code,
                status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING],
                user_email__in=users_having_usages
            )

            if assignments.count() == 0:
                continue

            parially_redeemed_assignments.append(assignments.first().id)

        return OfferAssignment.objects.filter(
            id__in=parially_redeemed_assignments).values('code', 'user_email').order_by('user_email')

    def _get_redeemed_usages(self, vouchers):
        """
        Returns a queryset containing unique voucher.code and user.email pairs from VoucherApplications.
        Only code and email pairs that have no corresponding active OfferAssignments are returned.
        """
        voucher_applications = VoucherApplication.objects.filter(voucher__in=vouchers)
        redeemed_voucher_application_ids = []
        for voucher_application in voucher_applications:
            unredeemed_voucher_assignments = OfferAssignment.objects.filter(
                code=voucher_application.voucher.code,
                user_email=voucher_application.user.email,
                status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING]
            )

            if unredeemed_voucher_assignments.count() == 0:
                redeemed_voucher_application_ids.append(voucher_application.id)

        return VoucherApplication.objects.filter(
            id__in=redeemed_voucher_application_ids
        ).values('voucher__code', 'user__email').distinct().order_by('user__email')

    @list_route(url_path=r'(?P<enterprise_id>.+)/overview')
    def overview(self, request, enterprise_id):     # pylint: disable=unused-argument
        """
        Overview of Enterprise coupons.
        Returns the following data:
            - Coupon ID
            - Coupon name.
            - Max number of codes available (Maximum coupon usage).
            - Number of codes.
            - Redemption count.
            - Valid from.
            - Valid end.
        """
        enterprise_coupons = self.get_queryset()
        coupon_id = self.request.query_params.get('coupon_id', None)
        if coupon_id is not None:
            coupon = get_object_or_404(enterprise_coupons, id=coupon_id)
            serializer = self.get_serializer(coupon)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            page = self.paginate_queryset(enterprise_coupons)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @detail_route(methods=['post'])
    def assign(self, request, pk):  # pylint: disable=unused-argument
        """
        Assign users by email to codes within the Coupon.
        """
        coupon = self.get_object()
        template = request.data.pop('template')
        serializer = CouponCodeAssignmentSerializer(
            data=request.data,
            context={'coupon': coupon, 'template': template}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=['post'])
    def revoke(self, request, pk):  # pylint: disable=unused-argument
        """
        Revoke users by email from codes within the Coupon.
        """
        coupon = self.get_object()
        email_template = request.data.pop('template', None)
        serializer = CouponCodeRevokeSerializer(
            data=request.data.get('assignments'),
            many=True,
            context={'coupon': coupon, 'template': email_template}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=['post'])
    def remind(self, request, pk):  # pylint: disable=unused-argument
        """
        Remind users of pending offer assignments by email.
        """
        coupon = self.get_object()
        email_template = request.data.pop('template', None)
        if not email_template:
            log_message_and_raise_validation_error(str('Template is required.'))

        if request.data.get('assignments'):
            assignments = request.data.get('assignments')
        else:
            # If no assignment is passed, send reminder to all assignments associated with the coupon.
            vouchers = coupon.attr.coupon_vouchers.vouchers.all()
            code_filter = request.data.get('code_filter')

            if not code_filter:
                raise serializers.ValidationError('code_filter must be specified')

            if code_filter == VOUCHER_NOT_REDEEMED:
                assignment_usages = self._get_not_redeemed_usages(vouchers)
            elif code_filter == VOUCHER_PARTIAL_REDEEMED:
                assignment_usages = self._get_partial_redeemed_usages(vouchers)
            else:
                raise serializers.ValidationError('Invalid code_filter specified: {}'.format(code_filter))

            assignments = [
                {
                    'code': assignment['code'],
                    'email': assignment['user_email']
                }
                for assignment in assignment_usages
            ]

        serializer = CouponCodeRemindSerializer(
            data=assignments,
            many=True,
            context={'coupon': coupon, 'template': email_template}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
