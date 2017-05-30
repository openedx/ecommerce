from __future__ import unicode_literals

import logging

import requests
import waffle
from dateutil.parser import parse
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from django.db import transaction

from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)


class MigratedCourse(object):
    def __init__(self, course_id, site_domain):
        self.course, _created = Course.objects.get_or_create(id=course_id)
        self.site_configuration = Site.objects.get(domain=site_domain).siteconfiguration

    def load_from_lms(self, access_token):
        """
        Loads course products from the LMS.

        Loaded data is NOT persisted until the save() method is called.
        """
        name, verification_deadline, modes = self._retrieve_data_from_lms(access_token)

        self.course.name = name
        self.course.verification_deadline = verification_deadline
        self.course.save()

        self._get_products(modes)

    def _build_lms_url(self, path):
        # We avoid using urljoin here because it URL-encodes the path, and some LMS APIs
        # are not capable of decoding these values.
        host = self.site_configuration.lms_url_root.strip('/')
        return '{host}/{path}'.format(host=host, path=path)

    def _query_commerce_api(self, headers):
        """Get course name and verification deadline from the Commerce API."""
        url = '{}/courses/{}/'.format(self._build_lms_url('api/commerce/v1'), self.course.id)
        timeout = settings.COMMERCE_API_TIMEOUT

        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise Exception('Unable to retrieve course name and verification deadline: [{status}] - {body}'.format(
                status=response.status_code,
                body=response.content
            ))

        data = response.json()
        logger.debug(data)

        course_name = data.get('name')
        if course_name is None:
            message = u'Unable to retrieve course name for {}.'.format(self.course.id)
            logger.error(message)
            raise Exception(message)

        course_verification_deadline = data['verification_deadline']
        course_verification_deadline = parse(course_verification_deadline) if course_verification_deadline else None

        return course_name.strip(), course_verification_deadline

    def _query_course_structure_api(self, access_token):
        """Get course name from the Course Structure API."""
        headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }

        url = self._build_lms_url('api/course_structure/v0/courses/{}/'.format(self.course.id))
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception('Unable to retrieve course name: [{status}] - {body}'.format(
                status=response.status_code,
                body=response.content
            ))

        data = response.json()
        logger.debug(data)

        course_name = data.get('name')
        if course_name is None:
            message = u'Aborting migration. No name is available for {}.'.format(self.course.id)
            logger.error(message)
            raise Exception(message)

        # A course without entries in the LMS CourseModes table must be an honor course, meaning
        # it has no verification deadline.
        course_verification_deadline = None

        return course_name.strip(), course_verification_deadline

    def _query_enrollment_api(self, headers):
        """Get modes and pricing from Enrollment API."""
        url = self._build_lms_url('api/enrollment/v1/course/{}?include_expired=1'.format(self.course.id))
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception('Unable to retrieve course modes: [{status}] - {body}'.format(
                status=response.status_code,
                body=response.content
            ))

        data = response.json()
        logger.debug(data)
        return data['course_modes']

    def _retrieve_data_from_lms(self, access_token):
        """
        Retrieves the course name and modes from the LMS.
        """
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        try:
            course_name, course_verification_deadline = self._query_commerce_api(headers)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                u"Calling Commerce API failed with: [%s]. Falling back to Course Structure API.",
                e.message
            )
            course_name, course_verification_deadline = self._query_course_structure_api(access_token)

        modes = self._query_enrollment_api(headers)

        return course_name, course_verification_deadline, modes

    def _get_products(self, modes):
        """ Creates/updates course seat products. """
        for mode in modes:
            certificate_type = Course.certificate_type_for_mode(mode['slug'])
            id_verification_required = Course.is_mode_verified(mode['slug'])
            price = mode['min_price']
            expires = mode.get('expiration_datetime')
            expires = parse(expires) if expires else None
            self.course.create_or_update_seat(
                certificate_type, id_verification_required, price, self.site_configuration.partner,
                expires=expires, remove_stale_modes=False
            )


class Command(BaseCommand):
    help = 'Migrate course modes and pricing from LMS to Oscar.'

    def add_arguments(self, parser):
        parser.add_argument('course_ids', nargs='+', type=str)

        parser.add_argument('--access_token',
                            action='store',
                            dest='access_token',
                            default=None,
                            help='OAuth2 access token used to authenticate against some LMS APIs.')
        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Save the migrated data to the database. If this is not set, '
                                 'migrated data will NOT be saved to the database.')
        parser.add_argument('--site',
                            action='store',
                            dest='site_domain',
                            default=None,
                            help='Domain for the ecommerce site providing the course.')

    def handle(self, *args, **options):
        course_ids = options.get('course_ids', [])
        access_token = options.get('access_token')
        site_domain = options.get('site_domain')
        if not access_token:
            logger.error('Courses cannot be migrated if no access token is supplied.')
            return

        if not site_domain:
            logger.error('Courses cannot be migrated without providing a site domain.')
            return

        for course_id in course_ids:
            course_id = unicode(course_id)
            try:
                with transaction.atomic():
                    migrated_course = MigratedCourse(course_id, site_domain)
                    migrated_course.load_from_lms(access_token)

                    course = migrated_course.course
                    msg = 'Retrieved info for {0} ({1}):\n'.format(course.id, course.name)
                    msg += '\t(cert. type, verified?, price, SKU, slug, expires)\n'

                    for seat in course.seat_products:
                        stock_record = seat.stockrecords.first()
                        data = (
                            getattr(seat.attr, 'certificate_type', ''),
                            seat.attr.id_verification_required,
                            '{0} {1}'.format(stock_record.price_currency, stock_record.price_excl_tax),
                            stock_record.partner_sku,
                            seat.slug,
                            seat.expires
                        )
                        msg += '\t{}\n'.format(data)

                    logger.info(msg)

                    if options.get('commit', False):
                        logger.info('Course [%s] was saved to the database.', course.id)
                        if waffle.switch_is_active('publish_course_modes_to_lms'):
                            course.publish_to_lms(access_token=access_token)
                        else:
                            logger.info('Data was not published to LMS because the switch '
                                        '[publish_course_modes_to_lms] is disabled.')
                    else:
                        logger.info('Course [%s] was NOT saved to the database.', course.id)
                        raise Exception('Forced rollback.')
            except Exception:  # pylint: disable=broad-except
                logger.exception('Failed to migrate [%s]!', course_id)
