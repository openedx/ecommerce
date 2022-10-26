import logging
from urllib.parse import urljoin, urlsplit

import waffle
from analytics import Client as SegmentClient
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from edx_django_utils import monitoring as monitoring_utils
from edx_rbac.models import UserRole, UserRoleAssignment
from edx_rest_api_client.client import OAuthAPIClient
from jsonfield.fields import JSONField
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import RequestException, Timeout
from simple_history.models import HistoricalRecords

from ecommerce.core.constants import ALL_ACCESS_CONTEXT, ALLOW_MISSING_LMS_USER_ID
from ecommerce.core.exceptions import MissingLmsUserIdException
from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.extensions.basket.constants import ENABLE_STRIPE_PAYMENT_PROCESSOR
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError
from ecommerce.extensions.payment.helpers import get_processor_class, get_processor_class_by_name

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
        verbose_name=_('[Deprecated] US Treasury SDN API URL'),
        max_length=255,
        blank=True
    )
    sdn_api_key = models.CharField(
        verbose_name=_('[Deprecated] US Treasury SDN API key'),
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
    hubspot_secret_key = models.CharField(
        verbose_name=_('Hubspot Portal Secret Key'),
        help_text=_('Secret key for Hubspot portal authentication'),
        max_length=255,
        blank=True
    )
    enable_microfrontend_for_basket_page = models.BooleanField(
        verbose_name=_('Enable Microfrontend for Basket Page'),
        help_text=_('Use the microfrontend implementation of the basket page instead of the server-side template'),
        blank=True,
        default=False
    )
    payment_microfrontend_url = models.URLField(
        verbose_name=_('Payment Microfrontend URL'),
        help_text=_('URL for the Payment Microfrontend (used if Enable Microfrontend for Basket Page is set)'),
        null=True,
        blank=True
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
                raise ValidationError(str(exc)) from exc

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

    def get_client_side_payment_processor_class(self, request):
        """ Returns the payment processor class to be used for client-side payments.

        If no processor is set, returns None.

         Returns:
             BasePaymentProcessor
        """
        desired_processor = self.client_side_payment_processor

        # Force client_side_payment_processor to be Stripe when waffle flag is set.
        # This allows slowly increasing the percentage of users redirected to Stripe.
        if waffle.flag_is_active(request, ENABLE_STRIPE_PAYMENT_PROCESSOR):
            desired_processor = 'stripe'

        if self.client_side_payment_processor:
            for processor in self._all_payment_processors():
                if processor.NAME == desired_processor:
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

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        # Clear Site cache upon SiteConfiguration changed
        Site.objects.clear_cache()
        super(SiteConfiguration, self).save(*args, **kwargs)

    def build_ecommerce_url(self, path=''):
        """
        Returns path joined with the appropriate ecommerce URL root for the current site.

        Returns:
            str
        """
        scheme = settings.PROTOCOL
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
    def enterprise_catalog_api_url(self):
        """ Returns the URL for the Enterprise Catalog service. """
        return settings.ENTERPRISE_CATALOG_API_URL

    @property
    def enterprise_grant_data_sharing_url(self):
        """ Returns the URL for the Enterprise data sharing permission view. """
        return self.build_enterprise_service_url('grant_data_sharing_permissions')

    @property
    def payment_domain_name(self):
        if self.enable_microfrontend_for_basket_page:
            return urlsplit(self.payment_microfrontend_url).netloc
        return self.site.domain

    @property
    def oauth_api_client(self):
        """
        This client is authenticated with the configured oauth settings and automatically cached.

        Returns:
            requests.Session: API client
        """
        return OAuthAPIClient(
            settings.BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL,
            settings.BACKEND_SERVICE_EDX_OAUTH2_KEY,
            settings.BACKEND_SERVICE_EDX_OAUTH2_SECRET,
        )

    @cached_property
    def embargo_api_url(self):
        """ Returns the URL for the embargo API """
        return self.build_lms_url('/api/embargo/v1/')

    @cached_property
    def consent_api_url(self):
        return self.build_lms_url('/consent/api/v1/')

    @cached_property
    def user_api_url(self):
        """
        Returns the API client to access the user API endpoint on LMS.

        Returns:
            str: The URL to access the LMS user API service.
        """
        return self.build_lms_url('/api/user/v1/')

    @cached_property
    def commerce_api_url(self):
        return self.build_lms_url('/api/commerce/v1/')

    @cached_property
    def credit_api_url(self):
        return self.build_lms_url('/api/credit/v1/')

    @cached_property
    def enrollments_api_url(self):
        return self.build_lms_url('/api/enrollment/v1/enrollment')

    @cached_property
    def entitlements_api_url(self):
        return self.build_lms_url('/api/entitlements/v1/entitlements/')


class User(AbstractUser):
    """
    Custom user model for use with python-social-auth via edx-auth-backends.
    """

    # This preserves the 30 character limit on last_name, avoiding a large migration
    # on the ecommerce_user table that would otherwise have come with Django 2.
    # See https://docs.djangoproject.com/en/3.0/releases/2.0/#abstractuser-last-name-max-length-increased-to-150
    last_name = models.CharField(_('last name'), max_length=30, blank=True)
    # Similarly, this avoids a large migration which otherwise would come with Django 3.2 upgrade
    # See, https://docs.djangoproject.com/en/3.2/releases/3.1/#abstractuser-first-name-max-length-increased-to-150
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    full_name = models.CharField(_('Full Name'), max_length=255, blank=True, null=True)
    tracking_context = JSONField(blank=True, null=True)
    email = models.EmailField(max_length=254, verbose_name='email address', blank=True, db_index=True)
    lms_user_id = models.IntegerField(
        null=True,
        blank=True,
        help_text=_(u'LMS user id'),
    )

    class Meta:
        get_latest_by = 'date_joined'
        db_table = 'ecommerce_user'

    @property
    def access_token(self):
        """
        Returns the access token from the extra data in the user's social auth.

        Note that a single user_id can be associated with multiple provider/uid combinations. For example:
            provider    uid             user_id
            edx-oidc    person          123
            edx-oauth2  person          123
            edx-oauth2  person@edx.org  123
        """
        try:
            return self.social_auth.order_by('-id').first().extra_data[u'access_token']  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            return None

    @classmethod
    def get_lms_user_attribute_using_email(cls, site, user_email, attribute='id'):
        """Returns a lms_user attribute by query LMS using email address.

        Args:
            site (Site): The site from which the LMS account API endpoint is created.
            user_email(str): Email address to search from LMS.
            attribute(str): LMS user attribute to get from LMS User. default is id (lms_user_id)

        Returns (str):
            Requested LMS User attribute or None if not found.
        """
        if user_email:
            try:
                response = cls.get_bulk_lms_users_using_emails(site, [user_email])
                return response[0][attribute]
            except (IndexError, KeyError):
                log.exception('Failed to get attribute [%s] for email: [%s]', attribute, user_email)
        return None

    @staticmethod
    def get_bulk_lms_users_using_emails(site, user_emails):
        """Returns a lms_users by query LMS using email address.

        Args:
            site (Site): The site from which the LMS account API endpoint is created.
            user_emails(list): Email address to search from LMS.

        Returns (list):
            LMS User objects or empty list if not found.
        """
        if user_emails:
            try:
                api_client = site.siteconfiguration.oauth_api_client
                api_url = urljoin(f"{site.siteconfiguration.user_api_url}/", "accounts/search_emails")
                response = api_client.post(api_url, json={'emails': user_emails})
                response.raise_for_status()
                return response.json()
            except Exception as error:  # pylint: disable=broad-except
                log.exception('Failed to get users for emails: [%s], error: [%s]', user_emails, error)
        return []

    def lms_user_id_with_metric(self, usage=None, allow_missing=False):
        """
        Returns the LMS user_id, or None if not found. Also sets a metric with the result.

        Arguments:
            usage (string): Optional. A description of how the returned id will be used. This will be included in log
                messages if the LMS user id cannot be found.
            allow_missing (boolean): True if the LMS user id is allowed to be missing. This affects the log messages
                and custom metrics. Defaults to False.

        Side effect:
            Writes custom metric.
        """
        # Read the lms_user_id from the ecommerce_user.
        lms_user_id = self.lms_user_id
        if lms_user_id:
            monitoring_utils.set_custom_metric('ecommerce_found_lms_user_id', lms_user_id)
            return lms_user_id

        # Could not find the lms_user_id
        if allow_missing:
            monitoring_utils.set_custom_metric('ecommerce_missing_lms_user_id_allowed', self.id)
            log.info(u'Could not find lms_user_id with metric for user %s for %s. Missing lms_user_id is allowed.',
                     self.id, usage, exc_info=True)
        else:
            monitoring_utils.set_custom_metric('ecommerce_missing_lms_user_id', self.id)
            log.warning(u'Could not find lms_user_id with metric for user %s for %s.', self.id, usage, exc_info=True)

        return None

    def add_lms_user_id(self, missing_metric_key, called_from, allow_missing=False):
        """
        If this user does not already have an LMS user id, look for the id in social auth. If the id can be found,
        add it to the user and save the user.

        The LMS user_id may already be present for the user. It may have been added from the jwt (see the
        EDX_DRF_EXTENSIONS.JWT_PAYLOAD_USER_ATTRIBUTE_MAPPING settings) or by a previous call to this method.

        Arguments:
            missing_metric_key (String): Key name for metric that will be created if the LMS user id cannot be found.
            called_from (String): Descriptive string describing the caller. This will be included in log messages.
            allow_missing (boolean): True if the LMS user id is allowed to be missing. This affects the log messages,
            custom metrics, and (in combination with the allow_missing_lms_user_id switch), whether an
            MissingLmsUserIdException is raised. Defaults to False.

        Side effect:
            If the LMS id cannot be found, writes custom metrics.
        """
        if not self.lms_user_id:
            # Check for the LMS user id in social auth
            lms_user_id_social_auth, social_auth_id = self._get_lms_user_id_from_social_auth()
            if lms_user_id_social_auth:
                self.lms_user_id = lms_user_id_social_auth
                self.save()
                log.info(u'Saving lms_user_id from social auth with id %s for user %s. Called from %s', social_auth_id,
                         self.id, called_from)
            else:
                # Could not find the LMS user id
                if allow_missing or waffle.switch_is_active(ALLOW_MISSING_LMS_USER_ID):
                    monitoring_utils.set_custom_metric('ecommerce_missing_lms_user_id_allowed', self.id)
                    monitoring_utils.set_custom_metric(missing_metric_key + '_allowed', self.id)

                    error_msg = (u'Could not find lms_user_id for user {user_id}. Missing lms_user_id is allowed. '
                                 u'Called from {called_from}'.format(user_id=self.id, called_from=called_from))
                    log.info(error_msg, exc_info=True)
                else:
                    monitoring_utils.set_custom_metric('ecommerce_missing_lms_user_id', self.id)
                    monitoring_utils.set_custom_metric(missing_metric_key, self.id)

                    error_msg = u'Could not find lms_user_id for user {user_id}. Called from {called_from}'.format(
                        user_id=self.id, called_from=called_from)
                    log.error(error_msg, exc_info=True)

                    raise MissingLmsUserIdException(error_msg)

    def _get_lms_user_id_from_social_auth(self):
        """
        Find the LMS user_id passed through social auth. Because a single user_id can be associated with multiple
        provider/uid combinations, start by checking the most recently saved social auth entry.

        Returns:
            (lms_user_id, social_auth_id): a tuple containing the LMS user id and the id of the social auth entry
                where the LMS user id was found. Returns None, None if the LMS user id was not found.
        """
        try:
            auth_entries = self.social_auth.order_by('-id')
            if auth_entries:
                for auth_entry in auth_entries:
                    lms_user_id_social_auth = auth_entry.extra_data.get(u'user_id')
                    if lms_user_id_social_auth:
                        return lms_user_id_social_auth, auth_entry.id
        except Exception:  # pylint: disable=broad-except
            log.warning(u'Exception retrieving lms_user_id from social_auth for user %s.', self.id, exc_info=True)
        return None, None

    def get_full_name(self):
        return self.full_name or super(User, self).get_full_name()

    def account_details(self, request):
        """ Returns the account details from LMS.

        Args:
            request (WSGIRequest): The request from which the LMS account API endpoint is created.

        Returns:
            A dictionary of account details.

        Raises:
            ConnectionError, RequestException and Timeout for failures in establishing a
            connection with the LMS account API endpoint.
        """
        try:
            api_client = request.site.siteconfiguration.oauth_api_client
            api_url = urljoin(f"{request.site.siteconfiguration.user_api_url}/", f"accounts/{self.username}")
            response = api_client.get(api_url)
            response.raise_for_status()
            return response.json()
        except (ReqConnectionError, RequestException, Timeout):
            log.exception(
                'Failed to retrieve account details for [%s]',
                self.username
            )
            raise

    def is_eligible_for_credit(self, course_key, site_configuration):
        """
        Check if a user is eligible for a credit course.
        Calls the LMS eligibility API endpoint and sends the username and course key
        query parameters and returns eligibility details for the user and course combination.

        Args:
            course_key (string): The course key for which the eligibility is checked for.

        Returns:
            A list that contains eligibility information, or empty if user is not eligible.

        Raises:
            ConnectionError, RequestException and Timeout for failures in establishing a
            connection with the LMS eligibility API endpoint.
        """
        query_strings = {
            'username': self.username,
            'course_key': course_key
        }
        try:
            client = site_configuration.oauth_api_client
            credit_url = urljoin(f"{site_configuration.credit_api_url}/", "eligibility/")
            response = client.get(credit_url, params=query_strings)
            response.raise_for_status()
            return response.json()
        except (ReqConnectionError, RequestException, Timeout):  # pragma: no cover
            log.exception(
                'Failed to retrieve eligibility details for [%s] in course [%s]',
                self.username,
                course_key
            )
            raise

    def deactivate_account(self, site_configuration):
        """Deactivate the user's account.

        Args:
            site_configuration (SiteConfiguration): The site configuration
                from which the LMS account API endpoint is created.

        Returns:
            Response from the deactivation API endpoint.
        """
        try:
            api_client = site_configuration.oauth_api_client
            accounts_api_url = urljoin(f"{site_configuration.user_api_url}/", f"accounts/{self.username}/deactivate/")
            response = api_client.post(accounts_api_url)
            response.raise_for_status()
            return response.json()
        except:  # pylint: disable=bare-except
            log.exception(
                'Failed to deactivate account for user [%s]',
                self.username
            )
            raise


class Client(User):
    """ Client Model. """


class BusinessClient(models.Model):
    """The model for the business client."""

    name = models.CharField(_('Name'), unique=True, max_length=255)
    enterprise_customer_uuid = models.UUIDField(
        verbose_name=_('EnterpriseCustomer UUID'),
        help_text=_('UUID for an EnterpriseCustomer from the Enterprise Service.'),
        null=True,
        blank=True,
    )

    history = HistoricalRecords()

    def __str__(self):
        return str(self.name)

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        if not self.name:
            log_message_and_raise_validation_error(
                'Failed to create BusinessClient. BusinessClient name may not be empty.'
            )
        super(BusinessClient, self).save(*args, **kwargs)


class EcommerceFeatureRole(UserRole):
    """
    User role definitions specific to Ecommerce.
     .. no_pii:
    """

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EcommerceFeatureRole {role}>".format(role=self.name)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class EcommerceFeatureRoleAssignment(UserRoleAssignment):
    """
    Model to map users to a EcommerceFeatureRole.
     .. no_pii:
    """

    role_class = EcommerceFeatureRole
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_index=True, on_delete=models.CASCADE)
    enterprise_id = models.UUIDField(blank=True, null=True, verbose_name='Enterprise Customer UUID')

    def get_context(self):
        """
        Return the enterprise customer id or `*` if the user has access to all resources.
        """
        enterprise_id = ALL_ACCESS_CONTEXT
        if self.enterprise_id:
            enterprise_id = str(self.enterprise_id)
        return enterprise_id

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EcommerceFeatureRoleAssignment for User {user} assigned to role {role}>".format(
            user=self.user.id,
            role=self.role.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
