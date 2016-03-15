from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield.fields import JSONField


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
        help_text=_("JSON string containing OAuth backend settings."),
        null=False,
        blank=False,
        default='{}'
    )

    class Meta(object):
        unique_together = ('site', 'partner')


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
    """The model for the business client."""
    pass
