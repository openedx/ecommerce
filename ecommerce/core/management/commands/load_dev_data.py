
import codecs
import datetime
import yaml

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from waffle.models import Flag

from ecommerce.tests.factories import UserFactory, PartnerFactory, SiteFactory, SiteConfigurationFactory
from ecommerce.courses.tests.factories import CourseFactory


class Command(BaseCommand):
    help = 'Create data for the ecommerce environment'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, required=True, help="Path to file where your data is specified.")

    def handle(self, *args, **options):
        with open(options["path"], 'r') as f:
            data_spec = yaml.safe_load(f)

        # Enable client-side checkout
        Flag.objects.update_or_create(name='enable_client_side_checkout', defaults={'everyone': True})

        for site_spec in data_spec['sites']:
            self.create_site(site_spec)

        for partner_spec in data_spec['partners']:
            self.create_partner(partner_spec)

        for site_configuration_spec in data_spec['site_configurations']:
            self.create_site_configuration(site_configuration_spec)

        for course_spec in data_spec['courses']:
            self.create_course(course_spec)


    def create_site(self, site_spec):
        site = SiteFactory(domain=site_spec['domain'])
        return site

    def create_partner(self, partner_spec):
        partner = PartnerFactory(**partner_spec)
        return partner

    def create_site_configuration(self, site_configuration_spec):
        lms_url_root = site_configuration_spec['lms_root_url']

        oauth_settings = {
            'SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT': lms_url_root,
            'SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL': '{lms_url_root}/logout'.format(lms_url_root=lms_url_root),
            'SOCIAL_AUTH_EDX_OAUTH2_ISSUERS': [lms_url_root],
            'SOCIAL_AUTH_EDX_OAUTH2_PUBLIC_URL_ROOT': site_configuration_spec['lms_public_root_url'],
            'SOCIAL_AUTH_EDX_OAUTH2_KEY': site_configuration_spec['sso_client_id'],
            'SOCIAL_AUTH_EDX_OAUTH2_SECRET': site_configuration_spec['sso_client_secret'],
            'BACKEND_SERVICE_EDX_OAUTH2_KEY': site_configuration_spec['backend_client_id'],
            'BACKEND_SERVICE_EDX_OAUTH2_SECRET': site_configuration_spec['backend_client_secret'],
        }

        partner = PartnerFactory(code=site_configuration_spec['partner'])
        site = SiteFactory(domain=site_configuration_spec['site'])

        site_configuration_values = {
            'site': site,
            'partner': partner,
            'lms_url_root': lms_url_root,
            'payment_processors': site_configuration_spec['payment_processors'],
            'client_side_payment_processor': site_configuration_spec['client_side_payment_processor'],
            'from_email': site_configuration_spec['from_email'],
            'oauth_settings': oauth_settings,
            'discovery_api_url': site_configuration_spec['discovery_api_url'],
            'enable_microfrontend_for_basket_page': site_configuration_spec['enable_microfrontend_for_basket_page'],
            'payment_microfrontend_url': site_configuration_spec['payment_microfrontend_url'],
        }

        site_config = SiteConfigurationFactory(**site_configuration_values)
        return site_config

    def create_course(self, course_spec):
        site = SiteFactory(domain=course_spec['site'])
        partner = PartnerFactory(code=course_spec['partner'])
        course_id = course_spec['course_key']

        course = CourseFactory(id=course_id, partner=partner, name=course_spec['name'])

        one_year = datetime.timedelta(days=365)
        expires = timezone.now() + one_year

        # Create the audit and verified seats
        audit_sku = None
        verified_sku = None
        if course.seat_products.exists():
            audit_seat = course.seat_products.filter(~Q(attributes__name='certificate_type')).first()
            audit_stock_record = audit_seat and audit_seat.stockrecords.first()
            if audit_stock_record:
                audit_sku = audit_stock_record.partner_sku
            verified_seat = course.seat_products.filter(attribute_values__value_text='verified').first()
            verified_stock_record = verified_seat and verified_seat.stockrecords.first()
            if verified_stock_record:
                verified_sku = verified_stock_record.partner_sku

        # Have to pass in the skus in case it is an update
        course.create_or_update_seat('', False, 0, sku=audit_sku)
        course.create_or_update_seat(
            'verified', True, course_spec['price'], expires=expires, create_enrollment_code=True, sku=verified_sku
        )
        # TODO(OEP-37 V0 implementors): during prototype, we used the publish_to_lms function to create corresponding ata
        # in lms. After review, we decided we did not want to intangle the IDAs in this way. If you decide the data created
        # by publish_to_lms is necessary for v0, please try to create it using just the yamls.
        # # Publish the data to the LMS
        # if course.publish_to_lms():
        #    msg = 'An error occurred while attempting to publish [{course_id}] to LMS'.format(course_id=course_id)
        #    self.stderr.write(self.style.ERROR(msg))
        # else:
        #     msg = 'Published course modes for [{course_id}] to LMS'.format(course_id=course_id)
        #     self.stdout.write(self.style.SUCCESS(msg))
