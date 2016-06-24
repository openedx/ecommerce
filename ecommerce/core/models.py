import datetime
import logging
from urlparse import urljoin

from analytics import Client as SegmentClient
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from edx_rest_api_client.client import EdxRestApiClient
from jsonfield.fields import JSONField
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError
from ecommerce.extensions.payment.helpers import get_processor_class_by_name, get_processor_class

log = logging.getLogger(__name__)


class SiteConfiguration(models.Model):
    """Custom Site model for custom sites/microsites.

    This model will enable the basic theming and payment processor
    configuration for each custom site.
    The multi-tenant implementation has one site per partner.
    """

    site = models.OneToOneField('sites.Site', null=False, blank=False)
    partner = models.ForeignKey('partner.Partner', null=False, blank=False)
    lms_url_root = models.URLField(
        verbose_name=_('LMS base url for custom site/microsite'),
        help_text=_("Root URL of this site's LMS (e.g. https://courses.stage.edx.org)"),
        null=False,
        blank=False
    )
    theme_scss_path = models.CharField(
        verbose_name=_('Path to custom site theme'),
        help_text=_('Path to scss files of the custom site theme'),
        max_length=255,
        null=False,
        blank=False
    )
    payment_processors = models.CharField(
        verbose_name=_('Payment processors'),
        help_text=_("Comma-separated list of processor names: 'cybersource,paypal'"),
        max_length=255,
        null=False,
        blank=False
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

    class Meta(object):
        unique_together = ('site', 'partner')

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

    def get_payment_processors(self):
        """
        Returns payment processor classes enabled for the corresponding Site

        Returns:
            list[BasePaymentProcessor]: Returns payment processor classes enabled for the corresponding Site
        """
        all_processors = [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]
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

    def get_from_email(self):
        """
        Returns the configured from_email value for the specified site.  If no from_email is
        available we return the base OSCAR_FROM_EMAIL setting

        Returns:
            string: Returns sender address for use in customer emails/alerts
        """
        return self.from_email or settings.OSCAR_FROM_EMAIL

    def clean_fields(self, exclude=None):
        """ Validates model fields """
        if not exclude or 'payment_processors' not in exclude:
            self._clean_payment_processors()

    @cached_property
    def segment_client(self):
        return SegmentClient(self.segment_key, debug=settings.DEBUG)

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

    @property
    def commerce_api_url(self):
        """ Returns the URL for the root of the Commerce API (hosted by LMS). """
        return self.build_lms_url('/api/commerce/v1/')

    @property
    def student_dashboard_url(self):
        """ Returns a URL to the student dashboard (hosted by LMS). """
        return self.build_lms_url('/dashboard')

    @property
    def enrollment_api_url(self):
        """ Returns the URL for the root of the Enrollment API. """
        return self.build_lms_url('/api/enrollment/v1/')

    @property
    def lms_heartbeat_url(self):
        """ Returns the URL for the LMS heartbeat page. """
        return self.build_lms_url('/heartbeat')

    @property
    def oauth2_provider_url(self):
        """ Returns the URL for the OAuth 2.0 provider. """
        return self.build_lms_url('/oauth2')

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
        access_token = cache.get(key)

        # pylint: disable=unsubscriptable-object
        if not access_token:
            url = '{root}/access_token'.format(root=self.oauth2_provider_url)
            access_token, expiration_datetime = EdxRestApiClient.get_oauth_access_token(
                url,
                self.oauth_settings['SOCIAL_AUTH_EDX_OIDC_KEY'],
                self.oauth_settings['SOCIAL_AUTH_EDX_OIDC_SECRET'],
                token_type='jwt'
            )

            expires = (expiration_datetime - datetime.datetime.utcnow()).seconds
            cache.set(key, access_token, expires)

        return access_token

    @cached_property
    def course_catalog_api_client(self):
        """
        Returns an API client to access the Course Catalog service.

        Returns:
            EdxRestApiClient: The client to access the Course Catalog service.
        """

        return EdxRestApiClient(settings.COURSE_CATALOG_API_URL, jwt=self.access_token)


class User(AbstractUser):
    """Custom user model for use with OIDC."""

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

    def is_user_already_enrolled(self, request, seat):
        """
        Check if a user is already enrolled in the course.
        Calls the LMS enrollment API endpoint and sends the course ID and username query parameters
        and returns the status of the user's enrollment in the course.

        Arguments:
            request (WSGIRequest): the request from which the LMS enrollment API endpoint is created.
            seat (Product): the seat for which the check is done if the user is enrolled in.

        Returns:
            A boolean value if the user is enrolled in the course or not.

        Raises:
            ConnectionError, SlumberBaseException and Timeout for failures in establishing a
            connection with the LMS enrollment API endpoint.
        """
        course_key = seat.attr.course_key
        try:
            api = EdxRestApiClient(
                request.site.siteconfiguration.build_lms_url('/api/enrollment/v1'),
                oauth_access_token=self.access_token,
                append_slash=False
            )
            status = api.enrollment(','.join([self.username, course_key])).get()
        except (ConnectionError, SlumberBaseException, Timeout) as ex:
            log.exception(
                'Failed to retrieve enrollment details for [%s] in course [%s], Because of [%s]',
                self.username,
                course_key,
                ex,
            )
            raise ex

        seat_type = mode_for_seat(seat)
        if status and status.get('mode') == seat_type and status.get('is_active'):
            return True
        return False


class Client(User):
    pass


class BusinessClient(models.Model):
    """The model for the business client."""

    name = models.CharField(_('Name'), unique=True, max_length=255, blank=False, null=False)

    def __str__(self):
        return self.name


def validate_configuration():
    """ Validates all existing SiteConfiguration models """
    for config in SiteConfiguration.objects.all():
        config.clean_fields()
