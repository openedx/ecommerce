"""
Django management command to unset superusers in ecommerce.
"""


import logging

from django.apps import apps
from django.core.management.base import BaseCommand

User = apps.get_model('core', 'User')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Revoke superuser access of all users on ecommerce.'

    def handle(self, *args, **options):
        all_superusers = User.objects.filter(is_superuser=True)
        superusers_count = all_superusers.count()
        if not superusers_count:
            logger.warning('No superusers found, falling back.')
            return
        updated_users = all_superusers.update(is_superuser=False)
        logger.info('Successfully Updated [%s] users', updated_users)
