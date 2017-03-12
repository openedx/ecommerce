import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from waffle.models import Switch

from ecommerce.extensions.api.v2.views.payments import PAYMENT_PROCESSOR_CACHE_KEY

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Switch)
def invalidate_processor_cache(*_args, **kwargs):
    """
    When Waffle switches for payment processors are toggled, the
    payment processor list view cache must be invalidated.
    """
    switch = kwargs['instance']
    parts = switch.name.split(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX)
    if len(parts) == 2:
        processor = parts[1]
        logger.info('Switched payment processor [%s] %s.', processor, 'on' if switch.active else 'off')
        cache.delete(PAYMENT_PROCESSOR_CACHE_KEY)
        logger.info('Invalidated payment processor cache after toggling [%s].', switch.name)
