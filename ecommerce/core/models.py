import datetime
import hashlib
import logging
from urlparse import urljoin, urlsplit, urlunsplit

from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from edx_django_utils.cache import TieredCache
from edx_rest_api_client.client import EdxRestApiClient
from jsonfield.fields import JSONField
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from analytics import Client as SegmentClient
from ecommerce.core.url_utils import get_lms_url
from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError
from ecommerce.extensions.payment.helpers import get_processor_class, get_processor_class_by_name
from ecommerce.journals.constants import JOURNAL_DISCOVERY_API_PATH  # TODO: journals dependency

log = logging.getLogger(__name__)


class SiteConfiguration(models.Model):
    """Tenant configuration.

    Each site/tenant should have an instance of this model. This model is responsible for
    providing databased-backed configuration specific to each site.
    """

    site = models.OneToOneField('sites.Site', null=False, blank=False, on_delete=models.CASCADE)
    partner = models.ForeignKey('partner.Partner', null=False, blank=False, on_delete=models.CASCADE)
    lms_url_root = models.URLField(
        verbose_name=_('LMS base url for custom site/microsite'),
        help_text=_("Root URL of this site's LMS (e.g. https://courses.stage.edx.org)"),
        null=False,
        blank=False
    )
    theme_scss_path = models.CharField(
        verbose_name=_('Path to custom site theme'),
        help_text='DEPRECATED: THIS FIELD WILL BE REMOVED!',
        max_length=255,
        null=True,
        blank=True
    )
    payment_processors = models.CharField(
        verbose_name=_('Payment processors'),
        help_text=_("Comma-separated list of processor names: 'cybersource,paypal'"),
        max_length=255,
        null=False,
        blank=False
    )
    client_side_payment_processor = models.CharField(
        verbose_name=_('Client-side payment processor'),
        help_text=_('Processor that will be used for client-side payments'),
        max_length=255,
        null=True,
        blank=True
    )
    oauth_settings = JSONField(
        verbose_name=_('OAuth settings'),
        help_text=_('JSON string containing OAuth backend settings.'),
        null=False,
        blank=False,
        default={}
    )
    segment_key = models.CharField(
        verbose_name=_('Segment key'),
        help_text=_('Segment write/API key.'),
        max_length=255,
        null=True,
        blank=True
    )
    from_email = models.CharField(
        verbose_name=_('From email'),
        help_text=_('Address from which emails are sent.'),
        max_length=255,
        null=True,
        blank=True
    )
    enable_enrollment_codes = models.BooleanField(
        verbose_name=_('Enable enrollment codes'),
        help_text=_('Enable the creation of enrollment codes.'),
        blank=True,
        default=False
    )
    payment_support_email = models.CharField(
        verbose_name=_('Payment support email'),
        help_text=_('Contact email for payment support issues.'),
        max_length=255,
        blank=True,
        default="support@example.com"
    )
    payment_support_url = models.CharField(
        verbose_name=_('Payment support url'),
        help_text=_('URL for payment support issues.'),
        max_length=255,
        blank=True
    )
    utm_cookie_name = models.CharField(
        verbose_name=_('UTM Cookie Name'),
        help_text=_('Name of cookie storing UTM data.'),
        max_length=255,
        blank=True,
        default="",
    )
    affiliate_cookie_name = models.CharField(
        verbose_name=_('Affiliate Cookie Name'),
        help_text=_('Name of cookie storing affiliate data.'),
        max_length=255,
        blank=True,
        default="",
    )
    send_refund_notifications = models.BooleanField(
        verbose_name=_('Send refund email notification'),
        blank=True,
        default=False
    )
    enable_sdn_check = models.BooleanField(
        verbose_name=_('Enable SDN check'),
        help_text=_('Enable SDN check at checkout.'),
        default=False
    )
    sdn_api_url = models.CharField(
        verbose_name=_('US Treasury SDN API URL'),
        max_length=255,
        blank=True
    )
    sdn_api_key = models.CharField(
        verbose_name=_('US Treasury SDN API key'),
        max_length=255,
        blank=True
    )
    sdn_api_list = models.CharField(
        verbose_name=_('SDN lists'),
        help_text=_('A comma-separated list of Treasury OFAC lists to check against.'),
        max_length=255,
        blank=True
    )
    require_account_activation = models.BooleanField(
        verbose_name=_('Require Account Activation'),
        help_text=_('Require users to activate their account before allowing them to redeem a coupon.'),
        default=True
    )
    optimizely_snippet_src = models.CharField(
        verbose_name=_('Optimizely snippet source URL'),
        help_text=_('This script will be loaded on every page.'),
        max_length=255,
        blank=True
    )
    enable_sailthru = models.BooleanField(
        verbose_name=_('Enable Sailthru Reporting'),
        help_text=_('Determines if purchases should be reported to Sailthru.'),
        default=False
    )
    base_cookie_domain = models.CharField(
        verbose_name=_('Base Cookie Domain'),
        help_text=_('Base cookie domain used to share cookies across services.'),
        max_length=255,
        blank=True,
        default='',
    )
    enable_embargo_check = models.BooleanField(
        verbose_name=_('Enable embargo check'),
        help_text=_('Enable embargo check at checkout.'),
        default=False
    )
    discovery_api_url = models.URLField(
        verbose_name=_('Discovery API URL'),
        null=False,
        blank=False,
    )
    # TODO: journals dependency
    journals_api_url = models.URLField(
        verbose_name=_('Journals Service API URL'),
        null=True,
        blank=True
    )
    enable_apple_pay = models.BooleanField(
        # Translators: Do not translate "Apple Pay"
        verbose_name=_('Enable Apple Pay'),
        default=False
    )
    enable_partial_program = models.BooleanField(
        verbose_name=_('Enable Partial Program Offer'),
        help_text=_('Enable the application of program offers to remaining unenrolled or unverified courses'),
        blank=True,
        default=False
    )

    @property
    def payment_processors_set(self):
        """
        Returns a set of enabled payment processor keys
        Returns:
            set[string]: Returns a set of enabled payment processor keys
        """
        return {raw_processor_value.strip() for raw_processor_value in self.payment_processors.split(',')}

    def _clean_payment_processors(self):
        """
        Validates payment_processors field value

        Raises:
            ValidationError: If `payment_processors` field contains invalid/unknown payment_processor names
        """
        value = self.payment_processors.strip()
        if not value:
            raise ValidationError('Invalid payment processors field: must not consist only of whitespace characters')

        processor_names = value.split(',')
        for name in processor_names:
            try:
                get_processor_class_by_name(name.strip())
            except ProcessorNotFoundError as exc:
                log.exception(
                    "Exception validating site configuration for site `%s` - payment processor %s could not be found",
                    self.site.id,
                    name
                )
                raise ValidationError(exc.message)

    def _clean_client_side_payment_processor(self):
        """
        Validates the client_side_payment_processor field value.


        Raises:
            ValidationError: If the field contains the name of a payment processor NOT found in the
            payment_processors field list.
        """
        value = (self.client_side_payment_processor or '').strip()
        if value and value not in self.payment_processors_set:
            raise ValidationError('Processor [{processor}] must be in the payment_processors field in order to '
                                  'be configured as a client-side processor.'.format(processor=value))

    def _all_payment_processors(self):
        """ Returns all processor classes declared in settings. """
        all_processors = [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]
        return all_processors

    def get_payment_processors(self):
        """
        Returns payment processor classes enabled for the corresponding Site

        Returns:
            list[BasePaymentProcessor]: Returns payment processor classes enabled for the corresponding Site
        """
        all_processors = self._all_payment_processors()
        all_processor_names = {processor.NAME for processor in all_processors}

        missing_processor_configurations = self.payment_processors_set - all_processor_names
        if missing_processor_configurations:
            processor_config_repr = ", ".join(missing_processor_configurations)
            log.warning(
                'Unknown payment processors [%s] are configured for site %s', processor_config_repr, self.site.id
            )

        return [
            processor for processor in all_processors
            if processor.NAME in self.payment_processors_set and processor.is_enabled()
        ]

    def get_client_side_payment_processor_class(self):
        """ Returns the payment processor class to be used for client-side payments.

        If no processor is set, returns None.

         Returns:
             BasePaymentProcessor
        """
        if self.client_side_payment_processor:
            for processor in self._all_payment_processors():
                if processor.NAME == self.client_side_payment_processor:
                    return processor

        return None

    def get_from_email(self):
        """
        Returns the configured from_email value for the specified site.  If no from_email is
        available we return the base OSCAR_FROM_EMAIL setting

        Returns:
            string: Returns sender address for use in customer emails/alerts
        """
        return self.from_email or settings.OSCAR_FROM_EMAIL

    @cached_property
    def segment_client(self):
        return SegmentClient(self.segment_key, debug=settings.DEBUG, send=settings.SEND_SEGMENT_EVENTS)

    def save(self, *args, **kwargs):
        # Clear Site cache upon SiteConfiguration changed
        Site.objects.clear_cache()
        super(SiteConfiguration, self).save(*args, **kwargs)

    def build_ecommerce_url(self, path=''):
        """
        Returns path joined with the appropriate ecommerce URL root for the current site.

        Returns:
            str
        """
        scheme = 'http' if settings.DEBUG else 'https'
        ecommerce_url_root = "{scheme}://{domain}".format(scheme=scheme, domain=self.site.domain)
        return urljoin(ecommerce_url_root, path)

    def build_lms_url(self, path=''):
        """
        Returns path joined with the appropriate LMS URL root for the current site.

        Returns:
            str
        """
        return urljoin(self.lms_url_root, path)

    def build_enterprise_service_url(self, path=''):
        """
        Returns path joined with the appropriate Enterprise service URL root for the current site.

        Returns:
            str
        """
        return urljoin(settings.ENTERPRISE_SERVICE_URL, path)

    def build_program_dashboard_url(self, uuid):
        """ Returns a URL to a specific student program dashboard (hosted by LMS). """
        return self.build_lms_url('/dashboard/programs/{}'.format(uuid))

    @property
    def student_dashboard_url(self):
        """ Returns a URL to the student dashboard (hosted by LMS). """
        return self.build_lms_url('/dashboard')

    @property
    def enrollment_api_url(self):
        """ Returns the URL for the root of the Enrollment API. """
        return self.build_lms_url('/api/enrollment/v1/')

    @property
    def oauth2_provider_url(self):
        """ Returns the URL for the OAuth 2.0 provider. """
        return self.build_lms_url('/oauth2')

    @property
    def enterprise_api_url(self):
        """ Returns the URL for the Enterprise service. """
        return settings.ENTERPRISE_API_URL

    @property
    def enterprise_grant_data_sharing_url(self):
        """ Returns the URL for the Enterprise data sharing permission view. """
        return self.build_enterprise_service_url('grant_data_sharing_permissions')

    @property
    def access_token(self):
        """ Returns an access token for this site's service user.

        The access token is retrieved using the current site's OAuth credentials and the client credentials grant.
        The token is cached for the lifetime of the token, as specified by the OAuth provider's response. The token
        type is JWT.

        Returns:
            str: JWT access token
        """
        key = 'siteconfiguration_access_token_{}'.format(self.id)
        access_token_cached_response = TieredCache.get_cached_response(key)
        if access_token_cached_response.is_found:
            return access_token_cached_response.value

        url = '{root}/access_token'.format(root=self.oauth2_provider_url)
        access_token, expiration_datetime = EdxRestApiClient.get_oauth_access_token(
            url,
            self.oauth_settings['BACKEND_SERVICE_EDX_OAUTH2_KEY'],  # pylint: disable=unsubscriptable-object
            self.oauth_settings['BACKEND_SERVICE_EDX_OAUTH2_SECRET'],  # pylint: disable=unsubscriptable-object
            token_type='jwt'
        )

        expires = (expiration_datetime - datetime.datetime.utcnow()).seconds
        TieredCache.set_all_tiers(key, access_token, expires)
        return access_token

    @cached_property
    def discovery_api_client(self):
        """
        Returns an API client to access the Discovery service.

        Returns:
            EdxRestApiClient: The client to access the Discovery service.
        """

        return EdxRestApiClient(self.discovery_api_url, jwt=self.access_token)

    # TODO: journals dependency
    @cached_property
    def journal_discovery_api_client(self):
        """
        Returns an Journal API client to access the Discovery service.

        Returns:
            EdxRestApiClient: The client to access the Journal API in the Discovery service.
        """
        split_url = urlsplit(self.discovery_api_url)
        journal_discovery_url = urlunsplit([
            split_url.scheme,
            split_url.netloc,
            JOURNAL_DISCOVERY_API_PATH,
            split_url.query,
            split_url.fragment
        ])

        return EdxRestApiClient(journal_discovery_url, jwt=self.access_token)

    @cached_property
    def embargo_api_client(self):
        """ Returns the URL for the embargo API """
        return EdxRestApiClient(self.build_lms_url('/api/embargo/v1'), jwt=self.access_token)

    @cached_property
    def enterprise_api_client(self):
        """
        Constructs a Slumber-based REST API client for the provided site.

        Example:
            site.siteconfiguration.enterprise_api_client.enterprise-learner(learner.username).get()

        Returns:
            EdxRestApiClient: The client to access the Enterprise service.

        """
        return EdxRestApiClient(self.enterprise_api_url, jwt=self.access_token)

    @cached_property
    def consent_api_client(self):
        return EdxRestApiClient(self.build_lms_url('/consent/api/v1/'), jwt=self.access_token, append_slash=False)

    @cached_property
    def user_api_client(self):
        """
        Returns the API client to access the user API endpoint on LMS.

        Returns:
            EdxRestApiClient: The client to access the LMS user API service.
        """
        return EdxRestApiClient(self.build_lms_url('/api/user/v1/'), jwt=self.access_token)

    @cached_property
    def commerce_api_client(self):
        return EdxRestApiClient(self.build_lms_url('/api/commerce/v1/'), jwt=self.access_token)

    @cached_property
    def credit_api_client(self):
        return EdxRestApiClient(self.build_lms_url('/api/credit/v1/'), jwt=self.access_token)

    @cached_property
    def enrollment_api_client(self):
        return EdxRestApiClient(self.build_lms_url('/api/enrollment/v1/'), jwt=self.access_token, append_slash=False)

    @cached_property
    def entitlement_api_client(self):
        return EdxRestApiClient(self.build_lms_url('/api/entitlements/v1/'), jwt=self.access_token)


class User(AbstractUser):
    """Custom user model for use with python-social-auth via edx-auth-backends."""

    full_name = models.CharField(_('Full Name'), max_length=255, blank=True, null=True)

    @property
    def access_token(self):
        try:
            return self.social_auth.first().extra_data[u'access_token']  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            return None

    tracking_context = JSONField(blank=True, null=True)

    class Meta(object):
        get_latest_by = 'date_joined'
        db_table = 'ecommerce_user'

    def get_full_name(self):
        return self.full_name or super(User, self).get_full_name()

    def account_details(self, request):
        """ Returns the account details from LMS.

        Args:
            request (WSGIRequest): The request from which the LMS account API endpoint is created.

        Returns:
            A dictionary of account details.

        Raises:
            ConnectionError, SlumberBaseException and Timeout for failures in establishing a
            connection with the LMS account API endpoint.
        """
        try:
            api = EdxRestApiClient(
                request.site.siteconfiguration.build_lms_url('/api/user/v1'),
                append_slash=False,
                jwt=request.site.siteconfiguration.access_token
            )
            response = api.accounts(self.username).get()
            return response
        except (ConnectionError, SlumberBaseException, Timeout):
            log.exception(
                'Failed to retrieve account details for [%s]',
                self.username
            )
            raise

    def is_eligible_for_credit(self, course_key):
        """
        Check if a user is eligible for a credit course.
        Calls the LMS eligibility API endpoint and sends the username and course key
        query parameters and returns eligibility details for the user and course combination.

        Args:
            course_key (string): The course key for which the eligibility is checked for.

        Returns:
            A list that contains eligibility information, or empty if user is not eligible.

        Raises:
            ConnectionError, SlumberBaseException and Timeout for failures in establishing a
            connection with the LMS eligibility API endpoint.
        """
        query_strings = {
            'username': self.username,
            'course_key': course_key
        }
        try:
            api = EdxRestApiClient(
                get_lms_url('api/credit/v1/'),
                oauth_access_token=self.access_token
            )
            response = api.eligibility().get(**query_strings)
        except (ConnectionError, SlumberBaseException, Timeout):  # pragma: no cover
            log.exception(
                'Failed to retrieve eligibility details for [%s] in course [%s]',
                self.username,
                course_key
            )
            raise
        return response

    def is_verified(self, site):
        """
        Check if a user has verified his/her identity.
        Calls the LMS verification status API endpoint and returns the verification status information.
        The status information is stored in cache, if the user is verified, until the verification expires.

        Args:
            site (Site): The site object from which the LMS account API endpoint is created.

        Returns:
            True if the user is verified, false otherwise.
        """
        try:
            cache_key = 'verification_status_{username}'.format(username=self.username)
            cache_key = hashlib.md5(cache_key).hexdigest()
            verification_cached_response = TieredCache.get_cached_response(cache_key)
            if verification_cached_response.is_found:
                return verification_cached_response.value

            api = EdxRestApiClient(
                site.siteconfiguration.build_lms_url('api/user/v1/'),
                oauth_access_token=self.access_token
            )
            response = api.accounts(self.username).verification_status().get()

            verification = response.get('is_verified', False)
            if verification:
                cache_timeout = int((parse(response.get('expiration_datetime')) - now()).total_seconds())
                TieredCache.set_all_tiers(cache_key, verification, cache_timeout)
            return verification
        except HttpNotFoundError:
            log.debug('No verification data found for [%s]', self.username)
            return False
        except (ConnectionError, SlumberBaseException, Timeout):
            msg = 'Failed to retrieve verification status details for [{username}]'.format(username=self.username)
            log.warning(msg)
            return False

    def deactivate_account(self, site_configuration):
        """Deactivate the user's account.

        Args:
            site_configuration (SiteConfiguration): The site configuration
                from which the LMS account API endpoint is created.

        Returns:
            Response from the deactivation API endpoint.
        """
        try:
            api = site_configuration.user_api_client
            return api.accounts(self.username).deactivate().post()
        except:  # pylint: disable=bare-except
            log.exception(
                'Failed to deactivate account for user [%s]',
                self.username
            )
            raise


class Client(User):
    pass


class BusinessClient(models.Model):
    """The model for the business client."""

    name = models.CharField(_('Name'), unique=True, max_length=255)
    enterprise_customer_uuid = models.UUIDField(
        verbose_name=_('EnterpriseCustomer UUID'),
        help_text=_('UUID for an EnterpriseCustomer from the Enterprise Service.'),
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.name:
            log_message_and_raise_validation_error(
                'Failed to create BusinessClient. BusinessClient name may not be empty.'
            )
        super(BusinessClient, self).save(*args, **kwargs)
