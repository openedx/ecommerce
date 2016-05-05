import logging

from analytics import Client as SegmentClient
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from jsonfield.fields import JSONField

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
        null=False,
        blank=False
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
        return {
            raw_processor_value.strip()
            for raw_processor_value in self.payment_processors.split(',')
        }

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
