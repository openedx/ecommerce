""" This command creates Sites, SiteThemes, SiteConfigurations and partners."""


import datetime
import fnmatch
import json
import logging
import os

from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from django.utils import timezone
from oscar.core.loading import get_model

from ecommerce.core.models import SiteConfiguration
from ecommerce.courses.models import Course
from ecommerce.theming.models import SiteTheme

logger = logging.getLogger(__name__)
Partner = get_model('partner', 'Partner')


class Command(BaseCommand):
    """Creates Sites, SiteThemes, SiteConfigurations and partners."""

    help = 'Creates Sites, SiteThemes, SiteConfigurations and partners.'
    dns_name = None
    theme_path = None
    configuration_filename = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--dns-name",
            type=str,
            help="Enter DNS name of sandbox.",
            required=True
        )

        parser.add_argument(
            "--theme-path",
            type=str,
            help="Enter theme directory path",
            required=True
        )

        parser.add_argument(
            "--devstack",
            action='store_true',
            help="Use devstack config, otherwise sandbox config is assumed",
        )

        parser.add_argument(
            "--demo_course",
            action='store_true',
            help="Create a demo course for testing this partner, used for whitelabel tests",
        )

    def _create_sites(self, site_domain, theme_dir_name, site_configuration, partner_code, demo_course):
        """
        Create Sites, SiteThemes, SiteConfigurations, and Courses (if requested)
        """
        site, _ = Site.objects.get_or_create(
            domain=site_domain,
            defaults={"name": theme_dir_name}
        )

        logger.info('Creating %s SiteTheme', site_domain)
        SiteTheme.objects.get_or_create(
            site=site,
            theme_dir_name=theme_dir_name
        )

        logger.info('Creating %s Partner', site_domain)
        partner, _ = Partner.objects.get_or_create(
            short_code=partner_code,
            defaults={
                "name": partner_code
            }
        )

        logger.info('Creating %s SiteConfiguration', site_domain)
        SiteConfiguration.objects.get_or_create(
            site=site,
            partner=partner,
            defaults=site_configuration
        )

        if demo_course:
            # Create the course, this is used in devstack whitelabel testing
            course_id = 'course-v1:{}+DemoX+Demo_Course'.format(partner_code)
            one_year = datetime.timedelta(days=365)
            expires = timezone.now() + one_year
            price = 159

            course, __ = Course.objects.update_or_create(id=course_id, partner=partner, defaults={
                'name': 'edX Demonstration Course',
                'verification_deadline': expires + one_year,
            })

            # Create the audit and verified seats
            course.create_or_update_seat('', False, 0)
            course.create_or_update_seat('verified', True, price, expires=expires, create_enrollment_code=True)
            logger.info('Created audit and verified seats for [%s]', course_id)

    def find(self, pattern, path):
        """
        Matched the given pattern in given path and returns the list of matching files
        """
        result = []
        for root, dirs, files in os.walk(path):  # pylint: disable=unused-variable
            for name in files:
                if fnmatch.fnmatch(name, pattern):
                    result.append(os.path.join(root, name))
        return result

    def _get_site_partner_data(self):
        """
        Reads the json files from theme directory and returns the site partner data in JSON format.
        """
        site_data = {}
        for config_file in self.find(self.configuration_filename, self.theme_path):
            logger.info('Reading file from %s', config_file)
            configuration_data = json.loads(
                json.dumps(
                    json.load(
                        open(config_file)
                    )
                ).replace("{dns_name}", self.dns_name)
            )['ecommerce_configuration']

            site_data[configuration_data['site_partner']] = {
                "partner_code": configuration_data['site_partner'],
                "site_domain": configuration_data['site_domain'],
                "theme_dir_name": configuration_data['theme_dir_name'],
                "configuration": configuration_data['configuration']
            }
        return site_data

    def handle(self, *args, **options):
        if options['devstack']:
            configuration_prefix = 'devstack'
        else:
            configuration_prefix = 'sandbox'

        self.configuration_filename = '{}_configuration.json'.format(configuration_prefix)
        self.dns_name = options['dns_name']
        self.theme_path = options['theme_path']

        logger.info("Using %s configuration...", configuration_prefix)
        logger.info('DNS name: %s', self.dns_name)
        logger.info('Theme path: %s', self.theme_path)

        all_sites = self._get_site_partner_data()
        for site_name, site_data in all_sites.items():
            logger.info('Creating %s Site', site_name)
            self._create_sites(
                site_data['site_domain'],
                site_data['theme_dir_name'],
                site_data['configuration'],
                site_data['partner_code'],
                options['demo_course']
            )
