"""
Django management command to un-enroll refunded android users.

Command is run by Jenkins job daily.
"""
import logging

import requests
from django.core.management.base import BaseCommand
from rest_framework import status

from ecommerce.core.models import SiteConfiguration

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Management command to un-enroll refunded android users.'

    def handle(self, *args, **options):
        site = SiteConfiguration.objects.first()
        refund_api_url = '{}/api/iap/v1/android/refund/'.format(site.build_ecommerce_url())
        logger.info("Sending request to un-enroll refunded android users")
        response = requests.get(refund_api_url)

        if response.status_code != status.HTTP_200_OK:
            logger.error("Failed to refund android users with status code %s", response.status_code)
