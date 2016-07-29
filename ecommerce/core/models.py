import datetime
import logging
from urlparse import urljoin

from analytics import Client as SegmentClient
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from edx_rest_api_client.client import EdxRestApiClient
from jsonfield.fields import JSONField
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError, PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE
from ecommerce.extensions.payment.processors import BasePaymentProcessor

log = logging.getLogger(__name__)


class SiteConfiguration(models.Model):
    """Custom Site model for custom sites/microsites.

    This model will enable the basic theming and payment processor
    configuration for each custom site.
    The multi-tenant implementation has one site per partner.
    """

    SINGLE_COLUMN = 'single_column'
    TWO_COLUMN = 'two_column'
    BASKET_LAYOUT_CHOICES = (
        (SINGLE_COLUMN, _('Single Column')),
        (TWO_COLUMN, _('Two Column'))
    )

    site = models.OneToOneField('sites.Site', null=False, blank=False)
    partner = models.ForeignKey('partner.Partner', null=False, blank=False)
    lms_url_root = models.URLField(
        verbose_name=_('LMS base url for custom site/microsite'),
        help_text=_("Root URL of this site's LMS (e.g. https://courses.stage.edx.org)"),
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
    basket_layout = models.CharField(
        verbose_name=_('Basket Page Layout'),
        help_text=_('The layout of the basket page.'),
        max_length=16,
        choices=BASKET_LAYOUT_CHOICES,
        default=SINGLE_COLUMN
    )
    checkout_template = models.CharField(
        verbose_name=_('Checkout Template'),
        help_text=_('The template to use for checkout.'),
        max_length=255,
        choices=getattr(settings, 'CHECKOUT_TEMPLATES'),
        default=getattr(settings, 'TWO_PAGE_CHECKOUT_TEMPLATE')
    )

    class Meta(object):
        unique_together = ('site', 'partner')

    def get_payment_processors(self):
        """
        Returns payment processor classes enabled for the corresponding Site

        Returns:
            dict[str, BasePaymentProcessor]: Returns dict of payment processor classes enabled for the
                                             corresponding Site keyed by payment processor name
        """
        payment_processors = {}
        for processor_class in BasePaymentProcessor.__subclasses__():
            processor = processor_class(self.site)
            if processor.is_enabled:
                payment_processors[processor.NAME] = processor

        return payment_processors

    def get_payment_processor_by_name(self, name):
        for processor_name, processor in self.get_payment_processors().iteritems():
            if processor_name == name:
                return processor

        raise ProcessorNotFoundError(
            PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE.format(name=name)
        )

    def get_default_payment_processor(self):
        return self.get_payment_processors()[0]

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
