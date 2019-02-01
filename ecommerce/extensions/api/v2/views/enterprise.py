from __future__ import unicode_literals

import logging
import waffle
from django.core.exceptions import ValidationError
from django.db.models import Count, F, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce
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
    CouponVoucherSerializer,
    EnterpriseCouponListSerializer,
    EnterpriseCouponOverviewListSerializer
)
from ecommerce.extensions.api.v2.utils import send_new_codes_notification_email
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.catalogue.utils import (
    attach_vouchers_to_coupon_product,
    create_coupon_product_and_stockrecord
)
from ecommerce.extensions.offer.constants import (
    OFFER_REDEEMED,
    OFFER_ASSIGNMENT_REVOKED,
    VOUCHER_UNASSIGNED,
    VOUCHER_UNREDEEMED,
    VOUCHER_REDEEMED,
    VOUCHER_PARTIAL_REDEEMED
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

DEPRECATED_COUPON_CATEGORIES = ['Bulk Enrollment']


class EnterpriseCustomerViewSet(generics.GenericAPIView):

    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get(self, request):
        site = request.site
        return Response(data={'results': get_enterprise_customers(site)})


class EnterpriseCouponViewSet(CouponViewSet):
    """ Coupon resource. """

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

    def get_voucher_type(self):
        """
        Returns voucher type of the coupon object.
        """
        coupon = self.get_object()
        return coupon.attr.coupon_vouchers.vouchers.first().usage

    def get_assigned_uredeemed_codes(self):
        """
        Returns the list of all those assigned codes which are not redeemed yet.
        """
        return OfferAssignment.objects.exclude(
            status__in=[OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED]
        ).values_list('code', flat=True)

    def get_redeemable_vouchers(self, coupon_vouchers):
        """
        Return vouchers which are redeemable. These vouchers are not fully redeemed.
        """
        vouchers_with_full_redemptions = self.get_fully_redeemed_coupon_vouchers(coupon_vouchers)
        redeemable_vouchers =  coupon_vouchers.exclude(pk__in=vouchers_with_full_redemptions)

        assigned_unredeemed_codes = self.get_assigned_uredeemed_codes()
        vouchers_with_some_assignments = redeemable_vouchers.filter(code__in=assigned_unredeemed_codes)
        vouchers_with_no_assignments = redeemable_vouchers.exclude(code__in=assigned_unredeemed_codes)

        # Also check how many assignments for this code.
        voucher_type = self.get_voucher_type()
        if voucher_type == Voucher.SINGLE_USE:
            redeemable_vouchers = redeemable_vouchers.exclude(code__in=assigned_unredeemed_codes)
        else:
            redeemable_vouchers_with_some_assignments = vouchers_with_some_assignments.filter(offers__max_global_applications__gt=F('num_orders') + F('offers__offerassignment'))
            redeemable_vouchers_with_no_assignments = vouchers_with_no_assignments.filter(offers__max_global_applications__gt=F('num_orders'))
            redeemable_vouchers = redeemable_vouchers_with_some_assignments | redeemable_vouchers_with_no_assignments
        return redeemable_vouchers

    def get_vouchers_with_free_slots(self, coupon_vouchers):
        """
        Return vouchers with free slots available.
        """
        # subquery to count number of unredeemed offer assignments of a code
        # the way this subquery is written is suggested in [django docs](https://docs.djangoproject.com/en/1.11/ref/models/expressions/#using-aggregates-within-a-subquery-expression)
        offerassignments = OfferAssignment.objects.filter(
            code=OuterRef('code')
        ).exclude(
            status__in=[OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED]
        ).order_by().values('code').annotate(assignment_count=Count('pk')).values('assignment_count')

        # Coalesce is used so that if there are no assigments than return 0
        offerassignments_subquery = Coalesce(Subquery(offerassignments, output_field=IntegerField()), 0)

        voucher_type = self.get_voucher_type()
        if voucher_type == Voucher.SINGLE_USE:
            qs_may_have_free_slots = coupon_vouchers.filter(num_orders=0)
            vouchers_with_free_slots = qs_may_have_free_slots.annotate(
                assignment_count=offerassignments_subquery
            ).filter(
                assignment_count=0,
                num_orders=0
            )
        else:
            qs_may_have_free_slots = coupon_vouchers.filter(offers__max_global_applications__gt=F('num_orders'))
            vouchers_with_free_slots = qs_may_have_free_slots.annotate(
                assignment_count=offerassignments_subquery
            ).filter(
                offers__max_global_applications__gt=F('assignment_count') + F('num_orders')
            )
        return vouchers_with_free_slots

    def get_vouchers_with_no_applications(self, coupon_vouchers):
        """
        Return vouchers with no voucher application.
        """
        return coupon_vouchers.filter(applications__isnull=True)

    def get_expanded_coupon_vouchers(self, coupon_vouchers):
        """
        Return vouchers against each voucher application, so if a
        voucher has two applications than this queryset will give 2 vouchers.
        """
        return Voucher.objects.filter(
            applications__voucher_id__in=coupon_vouchers
        )

    def get_unassigned_coupon_vouchers(self, coupon_vouchers):
        """
        Return only those vouchers which have free slots available.
        This will give us a list of vouchers which have any potential slot available for assignment,
        """
        # OLD 1
        # assigned_uredeemed_codes = self.get_assigned_uredeemed_codes()
        # redeemable_vouchers = self.get_redeemable_vouchers(coupon_vouchers)
        # unassigned_unredeemed_vouchers = redeemable_vouchers.exclude(code__in=assigned_uredeemed_codes)

        # OLD 2
        # unassigned_unredeemed_vouchers = self.get_redeemable_vouchers(coupon_vouchers)

        # NEW: Ammar
        unassigned_unredeemed_vouchers =  self.get_vouchers_with_free_slots(coupon_vouchers)
        return unassigned_unredeemed_vouchers

    def get_unredeemed_coupon_vouchers(self, coupon_vouchers):
        """
        Return assigned vouchers but never redeemed.
        """
        # FIXME: single use - edx-portal
        assigned_uredeemed_codes = self.get_assigned_uredeemed_codes()
        unredeemed_vouchers = coupon_vouchers.filter(code__in=assigned_uredeemed_codes)
        return unredeemed_vouchers

    def get_partial_redeemed_coupon_vouchers(self, coupon_vouchers):
        """
        Return assigned vouchers having at-least one redemption.
        """
        # Single use has only one redemption, so there would be no partial redemption in this case.
        voucher_type = self.get_voucher_type()
        if voucher_type == Voucher.SINGLE_USE:
            return coupon_vouchers.none()

        partially_redeemed_vouchers = coupon_vouchers.filter(num_orders__gte=1, offers__max_global_applications__gt=F('num_orders'))
        # TODO: add test for this.
        if voucher_type != Voucher.MULTI_USE_PER_CUSTOMER:
            partially_redeemed_vouchers = self.get_expanded_coupon_vouchers(partially_redeemed_vouchers)

        return partially_redeemed_vouchers

    def get_fully_redeemed_coupon_vouchers(self, coupon_vouchers):
        """
        Return vouchers that are fully redeemed, these vouchers do not have any assignment or redemption left.
        """
        # Single use has only one redemption.
        voucher_type = self.get_voucher_type()
        if voucher_type == Voucher.SINGLE_USE:
            return coupon_vouchers.filter(num_orders=1)

        redeemed_coupon_vouchers = coupon_vouchers.filter(offers__max_global_applications=F('num_orders'))
        if voucher_type != Voucher.MULTI_USE_PER_CUSTOMER:
            redeemed_coupon_vouchers = self.get_expanded_coupon_vouchers(redeemed_coupon_vouchers)
        return redeemed_coupon_vouchers

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

        coupon_code_filter = request.query_params.get('code_filter')
        if coupon_code_filter == VOUCHER_UNASSIGNED:
            # This filter will give us only those vouchers which have free slots available.
            coupon_vouchers = self.get_unassigned_coupon_vouchers(coupon_vouchers)
        elif coupon_code_filter == VOUCHER_UNREDEEMED:
            # This filter will give us assigned vouchers which are not redeemed yet.
            coupon_vouchers = self.get_unredeemed_coupon_vouchers(coupon_vouchers)
        elif coupon_code_filter == VOUCHER_PARTIAL_REDEEMED:
            # This filter will give us assigned vouchers having at-least one redemption.
            coupon_vouchers = self.get_partial_redeemed_coupon_vouchers(coupon_vouchers)
        elif coupon_code_filter == VOUCHER_REDEEMED:
            # This filter would return only those vouchers which are redeemed completely.
            coupon_vouchers = self.get_fully_redeemed_coupon_vouchers(coupon_vouchers)
        else:
            # Return all vouchers for coupon (unassigned + unredeemed + redeemed).
            # TODO: coupon_vouchers = self.get_unassigned_coupon_vouchers(coupon_vouchers) | self.get_unredeemed_coupon_vouchers(coupon_vouchers) | self.get_fully_redeemed_coupon_vouchers(coupon_vouchers)
            coupon_vouchers = self.get_expanded_coupon_vouchers(coupon_vouchers) | self.get_vouchers_with_no_applications(coupon_vouchers)

        if format is None:
            page = self.paginate_queryset(coupon_vouchers)
            serializer = CouponVoucherSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CouponVoucherSerializer(coupon_vouchers, many=True)
        return Response(serializer.data)

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
        serializer = CouponCodeRemindSerializer(
            data=request.data.get('assignments'),
            many=True,
            context={'coupon': coupon, 'template': email_template}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
