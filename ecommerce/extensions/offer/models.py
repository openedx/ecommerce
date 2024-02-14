import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import boto3
import pytz
from botocore.exceptions import ClientError
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from edx_django_utils.cache import TieredCache
from jsonfield.fields import JSONField
from oscar.apps.offer.abstract_models import (
    AbstractBenefit,
    AbstractCondition,
    AbstractConditionalOffer,
    AbstractRange,
    AbstractRangeProduct
)
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import RequestException, Timeout
from simple_history.models import HistoricalRecords
from threadlocals.threadlocals import get_current_request

from ecommerce.core.utils import get_cache_key, log_message_and_raise_validation_error
from ecommerce.extensions.offer.constants import (
    EMAIL_TEMPLATE_TYPES,
    NUDGE_EMAIL_CYCLE,
    NUDGE_EMAIL_TEMPLATE_TYPES,
    OFFER_ASSIGNED,
    OFFER_ASSIGNMENT_EMAIL_BOUNCED,
    OFFER_ASSIGNMENT_EMAIL_PENDING,
    OFFER_ASSIGNMENT_REVOKED,
    OFFER_MAX_USES_DEFAULT,
    OFFER_REDEEMED,
    SENDER_CATEGORY_TYPES,
    OfferUsageEmailTypes
)
from ecommerce.extensions.offer.utils import format_assigned_offer_email

OFFER_PRIORITY_ENTERPRISE = 10
OFFER_PRIORITY_VOUCHER = 20
OFFER_PRIORITY_MANUAL_ORDER = 100
LIMIT = models.Q(app_label='offer', model='offerassignmentemailtemplates') | \
    models.Q(app_label='offer', model='codeassignmentnudgeemailtemplates')

logger = logging.getLogger(__name__)

Voucher = get_model('voucher', 'Voucher')


class Benefit(AbstractBenefit):
    history = HistoricalRecords()

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        self.clean()
        super(Benefit, self).save(*args, **kwargs)  # pylint: disable=bad-super-call

    def clean(self):
        self.clean_value()
        super(Benefit, self).clean()  # pylint: disable=bad-super-call

    def clean_value(self):
        if self.value < 0:
            log_message_and_raise_validation_error(
                'Failed to create Benefit. Benefit value may not be a negative number.'
            )

    def clean_percentage(self):
        if not self.range:
            log_message_and_raise_validation_error('Percentage benefits require a product range')
        if self.value > 100:
            log_message_and_raise_validation_error('Percentage discount cannot be greater than 100')

    def _filter_for_paid_course_products(self, lines, applicable_range):
        """" Filters out products that aren't seats or entitlements or that don't have a paid certificate type. """
        return [
            line for line in lines
            if (line.product.is_seat_product or line.product.is_course_entitlement_product) and
            hasattr(line.product.attr, 'certificate_type') and
            line.product.attr.certificate_type.lower() in applicable_range.course_seat_types
        ]

    def _identify_uncached_product_identifiers(self, lines, domain, partner_code, query):
        """
        Checks the cache to see if each line is in the catalog range specified by the given query
        and tracks identifiers for which discovery service data is still needed.
        """
        uncached_course_run_ids = []
        uncached_course_uuids = []

        applicable_lines = lines
        for line in applicable_lines:
            if line.product.is_seat_product:
                product_id = line.product.course.id
            else:  # All lines passed to this method should either have a seat or an entitlement product
                product_id = line.product.attr.UUID

            cache_key = get_cache_key(
                site_domain=domain,
                partner_code=partner_code,
                resource='catalog_query.contains',
                course_id=product_id,
                query=query
            )
            in_catalog_range_cached_response = TieredCache.get_cached_response(cache_key)

            if not in_catalog_range_cached_response.is_found:
                if line.product.is_seat_product:
                    uncached_course_run_ids.append({'id': product_id, 'cache_key': cache_key, 'line': line})
                else:
                    uncached_course_uuids.append({'id': product_id, 'cache_key': cache_key, 'line': line})
            elif not in_catalog_range_cached_response.value:
                applicable_lines.remove(line)

        return uncached_course_run_ids, uncached_course_uuids, applicable_lines

    def get_applicable_lines(self, offer, basket, range=None):  # pylint: disable=redefined-builtin
        """
        Returns the basket lines for which the benefit is applicable.
        """
        applicable_range = range if range else self.range

        if applicable_range and applicable_range.catalog_query is not None:

            query = applicable_range.catalog_query
            applicable_lines = self._filter_for_paid_course_products(basket.all_lines(), applicable_range)

            site = basket.site
            partner_code = site.siteconfiguration.partner.short_code
            course_run_ids, course_uuids, applicable_lines = self._identify_uncached_product_identifiers(
                applicable_lines, site.domain, partner_code, query
            )

            if course_run_ids or course_uuids:
                # Hit Discovery Service to determine if remaining courses and runs are in the range.
                api_client = site.siteconfiguration.oauth_api_client
                discovery_api_url = urljoin(
                    f"{site.siteconfiguration.discovery_api_url}/",
                    "catalog/query_contains/"
                )
                try:
                    response = api_client.get(
                        discovery_api_url,
                        params={
                            "course_run_ids": ','.join([metadata['id'] for metadata in course_run_ids]),
                            "course_uuids": ','.join([metadata['id'] for metadata in course_uuids]),
                            "query": query,
                            "partner": partner_code
                        }
                    )
                    response.raise_for_status()
                    response = response.json()
                except (ReqConnectionError, RequestException, Timeout) as err:  # pylint: disable=bare-except
                    logger.exception(
                        '[Code Redemption Failure] Unable to apply benefit because we failed to query the '
                        'Discovery Service for catalog data. '
                        'User: %s, Offer: %s, Basket: %s, Message: %s',
                        basket.owner.username, offer.id, basket.id, err
                    )
                    raise Exception(
                        'Failed to contact Discovery Service to retrieve offer catalog_range data.'
                    ) from err

                logger.info(
                    "Discovery Service results for basket: [%s], offer: [%s], query: '%s', response: %s",
                    basket.id,
                    offer.id,
                    query,
                    response,
                )

                # Cache range-state individually for each course or run identifier and remove lines not in the range.
                for metadata in course_run_ids + course_uuids:
                    in_range = response[str(metadata['id'])]

                    # Convert to int, because this is what memcached will return, and the request cache should return
                    # the same value.
                    # Note: once the TieredCache is fixed to handle this case, we could remove this line.
                    in_range = int(in_range)
                    TieredCache.set_all_tiers(metadata['cache_key'], in_range, settings.COURSES_API_CACHE_TIMEOUT)

                    if not in_range:
                        applicable_lines.remove(metadata['line'])

            logger.info(
                "Basket [%s] with offer [%s] has applicable lines: %s",
                basket.id,
                offer.id,
                applicable_lines
            )
            return [(line.product.stockrecords.first().price_excl_tax, line) for line in applicable_lines]
        return super(Benefit, self).get_applicable_lines(offer, basket, range=range)  # pylint: disable=bad-super-call


class ConditionalOffer(AbstractConditionalOffer):
    DAILY = 'DAILY'
    WEEKLY = 'WEEKLY'
    MONTHLY = 'MONTHLY'
    USAGE_EMAIL_FREQUENCY_CHOICES = [
        (DAILY, 'Daily'),
        (WEEKLY, 'Weekly'),
        (MONTHLY, 'Monthly'),
    ]
    UPDATABLE_OFFER_FIELDS = ['email_domains', 'max_uses']
    email_domains = models.CharField(max_length=255, blank=True, null=True)
    sales_force_id = models.CharField(max_length=30, blank=True, null=True, default=None)
    salesforce_opportunity_line_item = models.CharField(max_length=30, blank=True, null=True)
    max_user_discount = models.DecimalField(
        verbose_name='Max user discount',
        max_digits=12,
        decimal_places=2,
        null=True,
        help_text='When an offer has given more discount than this threshold to orders of a user, then the offer '
                  'becomes unavailable for that user',
        blank=True
    )
    emails_for_usage_alert = models.TextField(
        verbose_name='Emails to receive offer usage alert',
        blank=True,
        help_text='Comma separated emails which will receive the offer usage alerts'
    )
    usage_email_frequency = models.CharField(
        max_length=8,
        choices=USAGE_EMAIL_FREQUENCY_CHOICES,
        default=DAILY,
    )
    site = models.ForeignKey(
        'sites.Site', verbose_name=_('Site'), null=True, blank=True, default=None, on_delete=models.CASCADE
    )
    partner = models.ForeignKey('partner.Partner', null=True, blank=True, on_delete=models.CASCADE)

    # Do not record the slug field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/openedx/course-discovery/pull/332
    history = HistoricalRecords(excluded_fields=['slug'])
    enterprise_contract_metadata = models.OneToOneField(
        'payment.EnterpriseContractMetadata',
        on_delete=models.CASCADE,
        null=True,
    )

    def save(self, *args, **kwargs):
        self.clean()
        super(ConditionalOffer, self).save(*args, **kwargs)  # pylint: disable=bad-super-call

    def clean(self):
        self.clean_email_domains()
        self.clean_max_global_applications()  # Our frontend uses the name max_uses instead of max_global_applications
        super(ConditionalOffer, self).clean()  # pylint: disable=bad-super-call

    def clean_email_domains(self):

        if self.email_domains:
            if not isinstance(self.email_domains, str):
                log_message_and_raise_validation_error(
                    'Failed to create ConditionalOffer. ConditionalOffer email domains must be of type string.'
                )

            email_domains_array = self.email_domains.split(',')

            if not email_domains_array[-1]:
                log_message_and_raise_validation_error(
                    'Failed to create ConditionalOffer. '
                    'Trailing comma for ConditionalOffer email domains is not allowed.'
                )

            for domain in email_domains_array:
                domain_parts = domain.split('.')
                error_message = 'Failed to create ConditionalOffer. ' \
                                'Email domain [{email_domain}] is invalid.'.format(email_domain=domain)

                # Conditions being tested:
                # - double hyphen not allowed
                # - must contain at least one dot
                # - top level domain must be at least two characters long
                # - hyphens are not allowed in top level domain
                # - numbers are not allowed in top level domain
                if any(['--' in domain,
                        len(domain_parts) < 2,
                        len(domain_parts[-1]) < 2,
                        re.findall(r'[-0-9]', domain_parts[-1])]):
                    log_message_and_raise_validation_error(error_message)

                for domain_part in domain_parts:
                    # - non of the domain levels can start or end with a hyphen before encoding
                    if domain_part.startswith('-') or domain_part.endswith('-'):
                        log_message_and_raise_validation_error(error_message)

                    # - all encoded domain levels must match given regex expression
                    if not re.match(r'^([a-z0-9-]+)$', domain_part.encode('idna').decode()):
                        log_message_and_raise_validation_error(error_message)

    def clean_max_global_applications(self):
        # enterprise offers have their own cleanup logic
        if self.priority != OFFER_PRIORITY_ENTERPRISE and self.max_global_applications is not None:
            if not isinstance(self.max_global_applications, int) or self.max_global_applications < 1:
                log_message_and_raise_validation_error(
                    'Failed to create ConditionalOffer. max_global_applications field must be a positive number.'
                )

    def is_email_valid(self, email):
        """
        Check if the email is within the email_domains if email_domains are set,
        else return True. If there is a domain with a sub domain in the list of
        valid email domains then the user's email needs to match exactly the
        domain and sub domain. If there is only a domain (without sub domains) in
        the list of valid email domains then the user's domain needs to match
        regardless of the subdomain.

        Examples:

            1)
                email_domains value: 'example.com'
                valid user email domains:
                    'example.com', 'sub1.example.com', 'sub2.example.com' etc.
                invalid user email domains:
                    'other.com' etc.

            2)
                email_domains value: 'sub.example.com'
                valid user email domain:
                    'sub.example.com'
                invalid user email domains:
                    'sub1.example.com', 'example.com' etc.

        Args:
            email (str): Email of the user.

        Returns:
            True if the email is valid or when there are no valid email domains set,
            False otherwise.
        """
        if self.email_domains:
            for domain in self.email_domains.split(','):
                pattern = r'(?P<username>.+)@(?P<subdomain>\w+\.)*{domain}'.format(domain=domain)
                match = re.match(pattern, email, re.IGNORECASE)
                if match and match.group(0) == email:
                    return True
            return False
        return True

    def is_condition_satisfied(self, basket):
        """
        In addition to Oscar's check to see if the condition is satisfied,
        a check for if basket owners email domain is within the allowed email domains.
        """
        if basket.owner and not self.is_email_valid(basket.owner.email):
            logger.warning('[Code Redemption Failure] Unable to apply offer because the user\'s email '
                           'does not meet the domain requirements. '
                           'User: %s, Offer: %s, Basket: %s', basket.owner.username, self.id, basket.id)
            return False

        if self.benefit.range and self.benefit.range.enterprise_customer:
            # If we are using enterprise conditional offers for enterprise coupons, the old style offer is not used.
            return False

        if self.benefit.range and self.benefit.range.catalog_query:
            # The condition is only satisfied if all basket lines are in the offer range
            num_lines = basket.all_lines().count()
            voucher = self.get_voucher()
            code = voucher and voucher.code
            username = basket.owner and basket.owner.username
            if voucher and num_lines > 1 and voucher.usage != Voucher.MULTI_USE:
                logger.warning('[Code Redemption Failure] Unable to apply offer because this Voucher '
                               'can only be used on single item baskets. '
                               'User: %s, Offer: %s, Basket: %s, Code: %s',
                               username, self.id, basket.id, code)
                return False
            is_satisfied = len(self.benefit.get_applicable_lines(self, basket)) == num_lines
            if not is_satisfied:
                logger.warning('[Code Redemption Failure] Unable to apply offer because this Voucher '
                               'is not valid for all courses in basket. '
                               'User: %s, Offer: %s, Basket: %s, Code: %s',
                               username, self.id, basket.id, code)

            return is_satisfied

        return super(ConditionalOffer, self).is_condition_satisfied(basket)  # pylint: disable=bad-super-call

    @property
    def is_current(self):
        start_date = self.start_datetime
        end_date = self.end_datetime
        is_current = False
        now = datetime.now(pytz.UTC)

        if start_date is None and end_date is None:
            is_current = True
        elif start_date and end_date is None:
            is_current = start_date <= now
        elif end_date and start_date is None:
            is_current = end_date > now
        else:
            is_current = start_date <= now < end_date

        return is_current


def validate_credit_seat_type(course_seat_types):
    if not isinstance(course_seat_types, str):
        log_message_and_raise_validation_error('Failed to create Range. Credit seat types must be of type string.')

    course_seat_types_list = course_seat_types.split(',')

    if len(course_seat_types_list) > 1 and 'credit' in course_seat_types_list:
        log_message_and_raise_validation_error(
            'Failed to create Range. Credit seat type cannot be paired with other seat types.'
        )

    if not set(course_seat_types_list).issubset(set(Range.ALLOWED_SEAT_TYPES)):
        log_message_and_raise_validation_error(
            'Failed to create Range. Not allowed course seat types {}. '
            'Allowed values for course seat types are {}.'.format(course_seat_types_list, Range.ALLOWED_SEAT_TYPES)
        )


class RangeProduct(AbstractRangeProduct):
    """
    Only extend to add a history table.
    """
    history = HistoricalRecords()


class Range(AbstractRange):
    UPDATABLE_RANGE_FIELDS = [
        'catalog_query',
        'course_seat_types',
        'course_catalog',
        'enterprise_customer',
        'enterprise_customer_catalog',
    ]
    ALLOWED_SEAT_TYPES = ['credit', 'professional', 'verified']
    catalog = models.ForeignKey(
        'catalogue.Catalog', blank=True, null=True, related_name='ranges', on_delete=models.CASCADE
    )
    catalog_query = models.TextField(blank=True, null=True)
    course_catalog = models.PositiveIntegerField(
        help_text=_('Course Catalog ID from the Discovery Service.'),
        null=True,
        blank=True
    )
    enterprise_customer = models.UUIDField(
        help_text=_('UUID for an EnterpriseCustomer from the Enterprise Service.'),
        null=True,
        blank=True,
    )

    enterprise_customer_catalog = models.UUIDField(
        help_text=_('UUID for an EnterpriseCustomerCatalog from the Enterprise Service.'),
        null=True,
        blank=True,
    )
    course_seat_types = models.CharField(
        max_length=255,
        validators=[validate_credit_seat_type],
        blank=True,
        null=True
    )

    # Do not record the slug field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/openedx/course-discovery/pull/332
    history = HistoricalRecords(excluded_fields=['slug'])

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        self.clean()
        super(Range, self).save(*args, **kwargs)  # pylint: disable=bad-super-call

    def clean(self):
        """ Validation for model fields. """
        if self.catalog and (self.course_catalog or self.catalog_query or self.course_seat_types):
            log_message_and_raise_validation_error(
                'Failed to create Range. Catalog and dynamic catalog fields may not be set in the same range.'
            )

        error_message = 'Failed to create Range. Either catalog_query or course_catalog must be given but not both ' \
                        'and course_seat_types fields must be set.'

        if self.catalog_query and self.course_catalog:
            log_message_and_raise_validation_error(error_message)
        elif (self.catalog_query or self.course_catalog) and not self.course_seat_types:
            log_message_and_raise_validation_error(error_message)
        elif self.course_seat_types and not (self.catalog_query or self.course_catalog):
            log_message_and_raise_validation_error(error_message)

        if self.course_seat_types:
            validate_credit_seat_type(self.course_seat_types)

    def catalog_contains_product(self, product):
        """
        Retrieve the results from using the catalog contains endpoint for
        catalog service for the catalog id contained in field "course_catalog".
        """
        request = get_current_request()
        partner_code = request.site.siteconfiguration.partner.short_code
        cache_key = get_cache_key(
            site_domain=request.site.domain,
            partner_code=partner_code,
            resource='catalogs.contains',
            course_id=product.course_id,
            catalog_id=self.course_catalog
        )
        cached_response = TieredCache.get_cached_response(cache_key)
        if cached_response.is_found:
            return cached_response.value

        api_client = request.site.siteconfiguration.oauth_api_client
        discovery_api_url = urljoin(
            f"{request.site.siteconfiguration.discovery_api_url}/",
            f"catalogs/{self.course_catalog}/contains/"
        )
        try:
            response = api_client.get(
                discovery_api_url,
                params={
                    "course_run_id": product.course_id
                }
            )
            response.raise_for_status()
            response = response.json()

            TieredCache.set_all_tiers(cache_key, response, settings.COURSES_API_CACHE_TIMEOUT)
            return response
        except (ReqConnectionError, RequestException, Timeout) as exc:
            logger.exception('[Code Redemption Failure] Unable to connect to the Discovery Service '
                             'for catalog contains endpoint. '
                             'Product: %s, Message: %s, Range: %s', product.id, exc, self.id)
            raise Exception('Unable to connect to Discovery Service for catalog contains endpoint.') from exc

    def contains_product(self, product):
        """
        Assert if the range contains the product.
        """
        # course_catalog is associated with course_seat_types.
        contains_product = super(Range, self).contains_product(product)  # pylint: disable=bad-super-call
        if self.course_catalog and self.course_seat_types:
            # Product certificate type should belongs to range seat types.
            if product.attr.certificate_type.lower() in self.course_seat_types:  # pylint: disable=unsupported-membership-test
                response = self.catalog_contains_product(product)
                # Range can have a catalog query and 'regular' products in it,
                # therefor an OR is used to check for both possibilities.
                contains_product = ((response['courses'][product.course_id]) or contains_product)

        elif self.catalog:
            contains_product = (
                product.id in self.catalog.stock_records.values_list('product', flat=True) or contains_product
            )

        if not contains_product:
            logger.warning('[Code Redemption Failure] Course catalog for Range does not contain the Product. '
                           'Product: %s, Range: %s', product.id, self.id)

        return contains_product

    contains = contains_product

    def num_products(self):
        return len(self.all_products())

    def all_products(self):
        if (self.catalog_query or self.course_catalog) and self.course_seat_types:
            # Backbone calls the Voucher Offers API endpoint which gets the products from the Discovery Service
            return []
        if self.catalog:
            catalog_products = [record.product for record in self.catalog.stock_records.all()]
            return catalog_products + list(super(Range, self).all_products())  # pylint: disable=bad-super-call
        return super(Range, self).all_products()  # pylint: disable=bad-super-call


class Condition(AbstractCondition):
    enterprise_customer_uuid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_('EnterpriseCustomer UUID'),
        db_index=True
    )
    # De-normalizing the EnterpriseCustomer name for optimization purposes.
    enterprise_customer_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('EnterpriseCustomer Name')
    )
    enterprise_customer_catalog_uuid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_('EnterpriseCustomerCatalog UUID')
    )
    program_uuid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_('Program UUID'),
        db_index=True
    )
    history = HistoricalRecords()

    class Meta:
        indexes = [
            models.Index(fields=['enterprise_customer_uuid', 'program_uuid'])
        ]


class OfferAssignment(TimeStampedModel):
    STATUS_CHOICES = (
        (OFFER_ASSIGNMENT_EMAIL_PENDING, _("Email to user pending.")),
        (OFFER_ASSIGNED, _("Code successfully assigned to user.")),
        (OFFER_REDEEMED, _("Code has been redeemed by user.")),
        (OFFER_ASSIGNMENT_EMAIL_BOUNCED, _("Email to user bounced.")),
        (OFFER_ASSIGNMENT_REVOKED, _("Code has been revoked for this user.")),
    )

    offer = models.ForeignKey('offer.ConditionalOffer', on_delete=models.CASCADE)
    code = models.CharField(max_length=128, db_index=True)
    user_email = models.EmailField(db_index=True)
    assignment_date = models.DateTimeField(blank=True, verbose_name='Offer Assignment Date', null=True)
    last_reminder_date = models.DateTimeField(blank=True, verbose_name='Last Reminder Date', null=True)
    revocation_date = models.DateTimeField(blank=True, verbose_name='Offer Revocation Date', null=True)
    status = models.CharField(
        max_length=255,
        db_index=True,
        choices=STATUS_CHOICES,
        default=OFFER_ASSIGNMENT_EMAIL_PENDING,
    )
    voucher_application = models.ForeignKey(
        'voucher.VoucherApplication',
        null=True,
        blank=True, on_delete=models.CASCADE
    )
    history = HistoricalRecords()

    class Meta:
        indexes = [
            models.Index(fields=['code', 'user_email']),
            models.Index(fields=['code', 'status']),
        ]

    def __str__(self):
        return "{code}-{email}".format(code=self.code, email=self.user_email)


class OfferAssignmentEmailAttempt(models.Model):
    """
    This model maps the message identifier received from ecommerce-worker to the OfferAssignment identifier.
    The primary application of this model is in the asynchronous email status update from ecommerce-worker.
    """
    offer_assignment = models.ForeignKey('offer.OfferAssignment', on_delete=models.CASCADE)
    send_id = models.CharField(max_length=255, unique=True)


class AbstractBaseEmailTemplate(TimeStampedModel):
    email_greeting = models.TextField(blank=True, null=True)
    email_closing = models.TextField(blank=True, null=True)
    email_subject = models.TextField(blank=True, null=True)
    active = models.BooleanField(
        help_text=_('Make a particular template version active.'),
        default=True,
    )
    name = models.CharField(max_length=255)

    class Meta:
        abstract = True


class OfferAssignmentEmailTemplates(AbstractBaseEmailTemplate):
    """
    This model keeps track of the Assign/Remind/Revoke templates saved via frontend portal.
    """
    enterprise_customer = models.UUIDField(help_text=_('UUID for an EnterpriseCustomer from the Enterprise Service.'))
    email_type = models.CharField(max_length=32, choices=EMAIL_TEMPLATE_TYPES)

    class Meta:
        ordering = ('enterprise_customer', '-active',)
        indexes = [
            models.Index(fields=['enterprise_customer', 'email_type'])
        ]

    @classmethod
    def get_template(cls, template_id=None):
        try:
            template = cls.objects.get(id=template_id)
        except ObjectDoesNotExist:
            template = None
        return template

    def __str__(self):
        return "{ec}-{email_type}-{active}".format(
            ec=self.enterprise_customer,
            email_type=self.email_type,
            active=self.active
        )


class TemplateFileAttachment(models.Model):
    name = models.CharField(max_length=256)
    size = models.PositiveIntegerField()
    url = models.URLField(max_length=300)
    template = models.ForeignKey(OfferAssignmentEmailTemplates, on_delete=models.CASCADE, related_name="email_files")

    def __str__(self):
        return 'name={}, size={}, url={}, template={}'.format(self.name, self.size, self.url, self.template)


@receiver(post_delete, sender=TemplateFileAttachment)
def delete_files_from_s3(sender, instance, using, **kwargs):  # pylint: disable=unused-argument
    delete_file_from_s3_with_key(instance.name)


def delete_file_from_s3_with_key(key):
    try:
        bucket_name = settings.ENTERPRISE_EMAIL_FILE_ATTACHMENTS_BUCKET_NAME
        session = boto3.Session()
        s3 = session.client('s3')
        s3.delete_object(Bucket=bucket_name, Key=key)
    except ClientError as error:
        logger.error(
            '[TemplateFileAttachment] Raised an error while deleting the object  %s,'
            'Message: %s',
            key,
            error.response['Error']['Message']
        )
    except Exception as ex:  # pylint: disable=broad-except
        logger.error(
            '[TemplateFileAttachment] Raised an error while deleting the object %s,'
            'Message: %s',
            key,
            ex
        )


class OfferAssignmentEmailSentRecord(TimeStampedModel):
    """
    This model keeps a record of all the emails sent to learners. Emails can be automatic or manual.
    """
    enterprise_customer = models.UUIDField(help_text=_('UUID for an EnterpriseCustomer from the Enterprise Service.'))
    email_type = models.CharField(max_length=32, choices=EMAIL_TEMPLATE_TYPES + NUDGE_EMAIL_TEMPLATE_TYPES)
    sender_category = models.CharField(max_length=32, choices=SENDER_CATEGORY_TYPES, null=True)
    user_email = models.EmailField(null=True)
    code = models.CharField(max_length=128, null=True)
    sender_id = models.PositiveIntegerField(null=True)
    receiver_id = models.PositiveIntegerField(null=True)
    template_content_type = models.ForeignKey(
        ContentType,
        limit_choices_to=LIMIT,
        null=True,
        on_delete=models.CASCADE,
    )
    template_id = models.PositiveIntegerField(null=True)
    template_content_object = GenericForeignKey('template_content_type', 'template_id')

    @classmethod
    def create_email_record(cls, enterprise_customer_uuid, email_type, template=None, sender_category=None, code=None,
                            user_email=None, receiver_id=None, sender_id=None):
        """
        Creates an instance of OfferAssignmentEmailSentRecord with the values passed.
        Arguments:
            enterprise_customer_uuid (str): The uuid of the enterprise that sent the email
            email_type (str): The type of the email sent e:g Assign, Remind or Revoke
            template (obj): The instance of the template used to send email e:g OfferAssignmentEmailTemplates
            sender_category (str): Category could be 'automatic' or 'manual'
            code (str): The coupon voucher code being assigned/reminded/revoked
            user_email (email): The email of the learner
            receiver_id (int): The lms_user_id of the receiver, NULL if the user hasn't created the account yet
            sender_id (int): The lms_user_id of the admin who sends the email
        """
        template_record = OfferAssignmentEmailSentRecord(
            user_email=user_email,
            code=code,
            receiver_id=receiver_id,
            sender_id=sender_id,
            sender_category=sender_category,
            template_content_object=template,
            enterprise_customer=enterprise_customer_uuid,
            email_type=email_type
        )
        template_record.save()
        return template_record

    def __str__(self):
        return "{ec}-{email_type}".format(
            ec=self.enterprise_customer,
            email_type=self.email_type,
        )


class OfferUsageEmail(TimeStampedModel):
    offer = models.ForeignKey('offer.ConditionalOffer', on_delete=models.CASCADE)
    email_type = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        choices=OfferUsageEmailTypes.CHOICES,
        help_text=("Which type of email was sent."),
    )
    offer_email_metadata = JSONField(default={})

    @classmethod
    def create_record(cls, email_type, offer, meta_data=None):
        """
        Create object by given data.
        """
        record = cls(email_type=email_type, offer=offer)
        if meta_data:
            record.offer_email_metadata = meta_data
        record.save()
        return record


class CodeAssignmentNudgeEmailTemplates(AbstractBaseEmailTemplate):
    """
    This model keeps track of all the saved templates for nudge emails.
    """
    email_type = models.CharField(max_length=32, choices=NUDGE_EMAIL_TEMPLATE_TYPES)

    @classmethod
    def get_nudge_email_template(cls, email_type):
        """
        Return the 'CodeAssignmentNudgeEmailTemplates' object of the
        given email_type or None in case of model exceptions.
        """
        nudge_email_template = None
        try:
            nudge_email_template = cls.objects.get(email_type=email_type, active=True)
        except (cls.DoesNotExist, cls.MultipleObjectsReturned) as exe:
            logger.error(
                '[CodeAssignmentNudgeEmailTemplates] Raised an error while getting the object for email_type %s,'
                'Message: %s',
                email_type,
                exe
            )
        return nudge_email_template

    def get_email_content(self, user_email, code, base_enterprise_url=''):
        """
        Return the formatted email body and subject.
        """
        email_body = None
        voucher_qs = Voucher.objects.filter(code=code)
        if voucher_qs.exists():
            voucher = voucher_qs.first()
            offer = voucher.best_offer
            max_usage_limit = offer.max_global_applications or OFFER_MAX_USES_DEFAULT

            email_body = format_assigned_offer_email(
                self.email_greeting,
                self.email_closing,
                user_email,
                code,
                max_usage_limit if offer.max_global_applications == Voucher.MULTI_USE_PER_CUSTOMER else 1,
                voucher.end_datetime,
                base_enterprise_url
            )
        else:
            logger.warning(
                '[Code Assignment Nudge Email] Unable to send the email for user_email: %s, code: %s because code does '
                'not have associated voucher.',
                user_email,
                code
            )
        return email_body, self.email_subject


class CodeAssignmentNudgeEmails(TimeStampedModel):
    """
    This model keeps track of all the nudge emails that are to be sent on a specific date. This information is based on
    the user's email subscription preferences.
    """

    def options_default():  # pylint: disable=no-method-argument
        return {"base_enterprise_url": ''}

    email_template = models.ForeignKey('offer.CodeAssignmentNudgeEmailTemplates', on_delete=models.CASCADE)
    code = models.CharField(max_length=128, db_index=True)
    user_email = models.EmailField(db_index=True)
    email_date = models.DateTimeField()
    already_sent = models.BooleanField(help_text=_('Email has been sent.'), default=False)
    is_subscribed = models.BooleanField(help_text=_('This user should receive email'), default=True)
    options = JSONField(default=options_default)

    class Meta:
        unique_together = (('email_template', 'code', 'user_email'),)

    @classmethod
    def subscribe_nudge_emails(cls, user_email, code, base_enterprise_url=''):
        """
        Subscribe the nudge email cycle for given user email and code.
        """
        now_datetime = datetime.now()
        for days, email_type in NUDGE_EMAIL_CYCLE.items():
            email_template = CodeAssignmentNudgeEmailTemplates.get_nudge_email_template(email_type=email_type)
            if email_template:
                data = {
                    'code': code,
                    'user_email': user_email,
                    'email_template': email_template,
                    'options': {'base_enterprise_url': base_enterprise_url},
                }
                if not cls.objects.filter(**data).exists():
                    data['email_date'] = now_datetime + relativedelta(days=int(days))
                    cls.objects.create(**data)
                    logger.info(
                        'Created a nudge email for user_email: %s, code: %s, email_type: %s, base_enterprise_url: %s',
                        user_email, code, email_type, base_enterprise_url,
                    )
            else:
                logger.warning(
                    'Unable to create a nudge email for user_email: %s, code: %s, email_type: %s, \
                    base_enterprise_url: %s',
                    user_email, code, email_type, base_enterprise_url,
                )

    @classmethod
    def unsubscribe_from_nudging(cls, codes, user_emails):
        """
        Unsubscribe users from receiving nudge emails.

        Args:
            codes (list): list of voucher codes
            user_emails (listt): list of user emails
        """
        cls.objects.filter(code__in=codes, user_email__in=user_emails, already_sent=False).update(is_subscribed=False)


from oscar.apps.offer.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
