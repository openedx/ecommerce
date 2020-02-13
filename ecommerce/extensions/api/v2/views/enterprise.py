from __future__ import absolute_import, unicode_literals

import logging

import six
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from edx_rbac.decorators import permission_required
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from rest_framework import generics, serializers, status
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet
from six.moves.urllib.parse import urlparse  # pylint: disable=import-error, ungrouped-imports
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME, DEFAULT_CATALOG_PAGE_SIZE
from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.coupons.utils import is_coupon_available
from ecommerce.enterprise.utils import (
    get_enterprise_catalog,
    get_enterprise_customer_catalogs,
    get_enterprise_customers,
    get_enterprise_catalog_config,
    get_learner_enrollment
)
from ecommerce.extensions.api.pagination import DatatablesDefaultPagination
from ecommerce.extensions.api.serializers import (
    CouponCodeAssignmentSerializer,
    CouponCodeRemindSerializer,
    CouponCodeRevokeSerializer,
    CouponSerializer,
    EnterpriseCouponListSerializer,
    EnterpriseCouponOverviewListSerializer,
    EnterpriseCouponSearchSerializer,
    NotAssignedCodeUsageSerializer,
    NotRedeemedCodeUsageSerializer,
    OfferAssignmentSummarySerializer,
    PartialRedeemedCodeUsageSerializer,
    RedeemedCodeUsageSerializer,
    CouponTraceSerializer
)
from ecommerce.extensions.api.v2.utils import get_enterprise_from_product, send_new_codes_notification_email
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.catalogue.utils import (
    attach_or_update_contract_metadata_on_coupon,
    attach_vouchers_to_coupon_product,
    create_coupon_product_and_stockrecord
)
from ecommerce.extensions.offer.constants import (
    OFFER_ASSIGNED,
    OFFER_ASSIGNMENT_EMAIL_BOUNCED,
    OFFER_ASSIGNMENT_EMAIL_PENDING,
    VOUCHER_NOT_ASSIGNED,
    VOUCHER_NOT_REDEEMED,
    VOUCHER_PARTIAL_REDEEMED,
    VOUCHER_REDEEMED
)
from ecommerce.extensions.offer.utils import update_assignments_for_multi_use_per_customer
from ecommerce.extensions.voucher.utils import (
    create_enterprise_vouchers,
    update_voucher_offer,
    update_voucher_with_enterprise_offer
)

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
CouponTrace = get_model('voucher', 'CouponTrace')
Line = get_model('basket', 'Line')
OfferAssignment = get_model('offer', 'OfferAssignment')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')
User = get_user_model()

DEPRECATED_COUPON_CATEGORIES = ['Bulk Enrollment']


class EnterpriseCustomerViewSet(generics.GenericAPIView):

    permission_classes = (IsAuthenticated, IsAdminUser,)
    queryset = ''

    def get(self, request):
        return Response(get_enterprise_customers(request))


class EnterpriseCustomerCatalogsViewSet(ViewSet):

    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get(self, request):
        endpoint_request_url = urlparse(request.build_absolute_uri())._replace(query=None).geturl()
        enterprise_catalogs = get_enterprise_customer_catalogs(
            request.site,
            endpoint_request_url,
            enterprise_customer_uuid=request.GET.get('enterprise_customer'),
            page=request.GET.get('page', '1'),
        )
        return Response(data=enterprise_catalogs)

    def retrieve(self, request, **kwargs):
        endpoint_request_url = urlparse(request.build_absolute_uri())._replace(query=None).geturl()
        try:
            catalog = get_enterprise_catalog(
                site=request.site,
                enterprise_catalog=kwargs.get('enterprise_catalog_uuid'),
                limit=request.GET.get('limit', DEFAULT_CATALOG_PAGE_SIZE),
                page=request.GET.get('page', '1'),
                endpoint_request_url=endpoint_request_url
            )
        except (ReqConnectionError, SlumberHttpBaseException, Timeout) as exc:
            logger.exception(
                'Unable to retrieve catalog for enterprise customer! customer: %s, Exception: %s',
                kwargs.get('enterprise_catalog_uuid'),
                exc
            )
            return Response(
                {'error': 'Unable to retrieve enterprise catalog. Exception: {}'.format(six.text_type(exc))},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(catalog)


class OfferAssignmentSummaryViewSet(ModelViewSet):
    """
    Viewset to return OfferAssignment coupon data.
    """

    permission_classes = (IsAuthenticated,)

    serializer_class = OfferAssignmentSummarySerializer
    pagination_class = DatatablesDefaultPagination
    http_method_names = ['get', 'head']

    def get_queryset(self):
        """
        Return a list of dictionaries to be serialized.

        Each dictionary contains one offerAssignment object, and the count of
        how many total offerAssignment objects the DB returned with the same
        code, as a way of "rolling up" offerAssignments a user has.
        """
        queryset = OfferAssignment.objects.filter(
            user_email=self.request.user.email,
            status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING],
        ).select_related(
            'offer__benefit',
            'offer__condition',
        )
        offer_assignments_with_counts = {}
        for offer_assignment in queryset:
            if offer_assignment.code not in offer_assignments_with_counts:
                # Note that we can get away with just dropping in the first
                # offerAssignment object of particular code that we see
                # because most of the data we are returning lives on related
                # objects that each of these offerAssignments share (e.g. the benefit)
                offer_assignments_with_counts[offer_assignment.code] = {
                    'count': 1,
                    'obj': offer_assignment,
                }
            else:
                offer_assignments_with_counts[offer_assignment.code]['count'] += 1
        return list(offer_assignments_with_counts.values())


class EnterpriseCouponViewSet(CouponViewSet):
    """ Coupon resource. """
    pagination_class = DatatablesDefaultPagination

    def get_queryset(self):
        filter_kwargs = {
            'product_class__name': COUPON_PRODUCT_CLASS_NAME,
            'attributes__code': 'enterprise_customer_uuid',
        }
        enterprise_id = self.kwargs.get('enterprise_id')
        if enterprise_id:
            filter_kwargs['attribute_values__value_text'] = enterprise_id

        coupons = Product.objects.filter(**filter_kwargs)

        if self.request.query_params.get('filter') == 'active':
            active_coupon = ~Q(attributes__code='inactive') | Q(
                attributes__code='inactive',
                attribute_values__value_boolean=False
            )
            coupons = coupons.filter(active_coupon)

        return coupons.distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return EnterpriseCouponListSerializer
        if self.action == 'overview':
            return EnterpriseCouponOverviewListSerializer
        return CouponSerializer

    def validate_access_for_enterprise(self, request_data):
        # Bypass old-style coupons in enterprise view.
        pass

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
            cleaned_voucher_data.get('notify_email'),
            cleaned_voucher_data['enterprise_customer']
        )
        attach_or_update_contract_metadata_on_coupon(
            coupon_product,
            discount_type=cleaned_voucher_data['contract_discount_type'],
            discount_value=cleaned_voucher_data['contract_discount_value'],
            amount_paid=cleaned_voucher_data['prepaid_invoice_amount'],
        )

        return coupon_product

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
            update_assignments_for_multi_use_per_customer(voucher)

        if coupon_was_migrated:
            super(EnterpriseCouponViewSet, self).update_range_data(request_data, vouchers)

    @detail_route(url_path='codes', permission_classes=[IsAuthenticated])
    @permission_required(
        'enterprise.can_view_coupon', fn=lambda request, pk, format=None: get_enterprise_from_product(pk)
    )
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
                status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_BOUNCED, OFFER_ASSIGNMENT_EMAIL_PENDING]
            ).exclude(user_email__in=users_having_usages)

            if assignments.count() == 0:
                continue

            unredeemed_assignments.extend(assignments.values_list('id', flat=True))

        return OfferAssignment.objects.filter(
            id__in=unredeemed_assignments).values('code', 'user_email').order_by('user_email').distinct()

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

    @list_route(url_path=r'(?P<enterprise_id>.+)/search', permission_classes=[IsAuthenticated])
    @permission_required('enterprise.can_view_coupon', fn=lambda request, enterprise_id: enterprise_id)
    def search(self, request, enterprise_id):     # pylint: disable=unused-argument
        """
        Return coupon information based on query param values provided.
        """
        user_email = self.request.query_params.get('user_email', None)
        voucher_code = self.request.query_params.get('voucher_code', None)
        if not (user_email or voucher_code):
            raise Http404("No search query parameter provided.")
        try:
            user = User.objects.get(email=user_email)
        except ObjectDoesNotExist:
            user = None

        enterprise_vouchers = self._collect_enterprise_vouchers_for_search(
            user_email,
            user,
            voucher_code
        )

        redemptions_and_assignments = self._form_search_response_data_from_vouchers(
            enterprise_vouchers,
            user_email,
            user,
        )

        page = self.paginate_queryset(redemptions_and_assignments)
        serializer = EnterpriseCouponSearchSerializer(
            page,
            many=True,
        )
        return self.get_paginated_response(serializer.data)

    def _collect_enterprise_vouchers_for_search(self, user_email, user, voucher_code):
        """
        Gather vouchers based on offerAssignments and voucherApplications
        associated with the user (and enterprise specified in request url)

        Returns queryset of Voucher objects, with related tables prefetched.
        """

        # We want vouchers associated with this enterprise. Note:
        # self.get_queryset() here filters (coupon) products out for
        # the enterprise_id value handed to this view
        enterprise_vouchers = Voucher.objects.filter(
            coupon_vouchers__coupon__in=self.get_queryset()
        )
        # When search is made by code, only one voucher will exist so return it directly
        if not user_email:
            voucher = enterprise_vouchers.filter(code=voucher_code)
            return voucher
        # We want vouchers with OfferAssignments related to the user email
        # that do not have a voucher_application (aka they have been assigned
        # but not redeemed)
        no_voucher_application = Q(voucher_application__isnull=True)
        offer_assignments = OfferAssignment.objects.filter(
            no_voucher_application,
            user_email=user_email,
            status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING],
        )
        vouchers_from_offer_assignments = Q(
            offers__offerassignment__in=offer_assignments
        )
        # We also want vouchers with VoucherApplications related to the user
        # but only if the user exists (there is a chance it does not, as code
        # assignment only requires an email, and not an account on the system)
        if user is not None:
            voucher_applications = VoucherApplication.objects.filter(
                user=user
            )
            vouchers_from_voucher_applications = Q(
                applications__in=voucher_applications
            )
            enterprise_vouchers = enterprise_vouchers.filter(
                vouchers_from_offer_assignments | vouchers_from_voucher_applications
            )
        else:
            enterprise_vouchers = enterprise_vouchers.filter(
                vouchers_from_offer_assignments
            )

        return enterprise_vouchers.distinct().prefetch_related(
            'coupon_vouchers__coupon',
            'applications',
            'applications__order__lines__product__course',
        )

    def _form_search_response_data_from_vouchers(self, vouchers, user_email, user):
        """
        Build a list of dictionaries that contains the relevant information
        for each voucher_application (redemption) or offer_assignment (assignment).

        Returns a list of dictionaries to be handed to the serializer for
        construction of pagination.
        """

        def _prepare_redemption_data(coupon_data, offer_assignment=None):
            """
            Prepares redemption data for the received voucher in coupon_data
            """
            redemption_data = dict(coupon_data)
            redemption_data['course_title'] = None
            redemption_data['course_key'] = None
            redemption_data['redeemed_date'] = None
            redemption_data['user_email'] = offer_assignment.user_email if offer_assignment else None
            redemptions_and_assignments.append(redemption_data)

        redemptions_and_assignments = []
        for voucher in vouchers:
            coupon_data = {
                'coupon_id': voucher.coupon_vouchers.first().coupon.id,
                'coupon_name': voucher.coupon_vouchers.first().coupon.title,
                'code': voucher.code,
                'voucher_id': voucher.id,
            }
            if user is not None:
                for application in voucher.applications.filter(user_id=user.id):
                    redemption_data = dict(coupon_data)
                    redemption_data['course_title'] = application.order.lines.first().product.course.name
                    redemption_data['course_key'] = application.order.lines.first().product.course.id
                    redemption_data['redeemed_date'] = application.date_created
                    redemptions_and_assignments.append(redemption_data)

            no_voucher_application = Q(voucher_application__isnull=True)
            filter_kwargs = {
                'code': voucher.code,
                'status__in': [OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING],
            }
            if user_email:
                filter_kwargs['user_email'] = user_email
            offer_assignments = OfferAssignment.objects.filter(
                no_voucher_application,
                **filter_kwargs).distinct()
            coupon_data['is_assigned'] = offer_assignments.count()
            # For the case when an unassigned voucher code is searched
            if offer_assignments.count() == 0:
                if not user_email:
                    _prepare_redemption_data(coupon_data)
            else:
                for offer_assignment in offer_assignments:
                    _prepare_redemption_data(coupon_data, offer_assignment)
        return redemptions_and_assignments

    @list_route(url_path=r'(?P<enterprise_id>.+)/overview', permission_classes=[IsAuthenticated])
    @permission_required('enterprise.can_view_coupon', fn=lambda request, enterprise_id: enterprise_id)
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

        page = self.paginate_queryset(enterprise_coupons)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def _validate_coupon_availablity(self, coupon, message):
        """
        Raise ValidationError with specified message if coupon is not available.
        """
        if not is_coupon_available(coupon):
            raise DRFValidationError({'error': message})

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated])
    @permission_required('enterprise.can_assign_coupon', fn=lambda request, pk: get_enterprise_from_product(pk))
    def assign(self, request, pk):  # pylint: disable=unused-argument
        """
        Assign users by email to codes within the Coupon.
        """
        coupon = self.get_object()
        self._validate_coupon_availablity(coupon, 'Coupon is not available for code assignment')
        greeting = request.data.pop('template_greeting', '')
        closing = request.data.pop('template_closing', '')
        serializer = CouponCodeAssignmentSerializer(
            data=request.data,
            context={'coupon': coupon, 'greeting': greeting, 'closing': closing}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated])
    @permission_required('enterprise.can_assign_coupon', fn=lambda request, pk: get_enterprise_from_product(pk))
    def revoke(self, request, pk):  # pylint: disable=unused-argument
        """
        Revoke users by email from codes within the Coupon.
        """
        coupon = self.get_object()
        self._validate_coupon_availablity(coupon, 'Coupon is not available for code revoke')
        greeting = request.data.pop('template_greeting', '')
        closing = request.data.pop('template_closing', '')
        serializer = CouponCodeRevokeSerializer(
            data=request.data.get('assignments'),
            many=True,
            context={'coupon': coupon, 'greeting': greeting, 'closing': closing}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated])
    @permission_required('enterprise.can_assign_coupon', fn=lambda request, pk: get_enterprise_from_product(pk))
    def remind(self, request, pk):  # pylint: disable=unused-argument
        """
        Remind users of pending offer assignments by email.
        """
        coupon = self.get_object()
        self._validate_coupon_availablity(coupon, 'Coupon is not available for code remind')
        greeting = request.data.pop('template_greeting', '')
        closing = request.data.pop('template_closing', '')

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
            context={'coupon': coupon, 'greeting': greeting, 'closing': closing}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EnterpriseCouponTraceListView(generics.ListAPIView):
    model = CouponTrace
    permission_classes = (IsAuthenticated,)
    serializer_class = CouponTraceSerializer

    def get_queryset(self):
        coupon_code = self.request.query_params.get('coupon_code')
        username = self.request.query_params.get('username')

        queryset = self.model.objects.all()
        if coupon_code:
            queryset = queryset.filter(coupon_code__iexact=coupon_code)
        if username:
            queryset = queryset.filter(user__username__icontains=username)

        return queryset
