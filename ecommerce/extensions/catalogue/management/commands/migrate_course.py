from __future__ import unicode_literals
import logging
from optparse import make_option

import dateutil.parser
from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
import requests

from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)


class MigratedCourse(object):
    def __init__(self, course_id):
        self.course, __ = Course.objects.get_or_create(id=course_id)

    def load_from_lms(self, access_token):
        """
        Loads course products from the LMS.

        Loaded data is NOT persisted until the save() method is called.
        """
        name, modes = self._retrieve_data_from_lms(access_token)
        self.course.name = name
        self.course.save()
        self._get_products(modes)

    def _build_lms_url(self, path):
        # We avoid using urljoin here because it URL-encodes the path, and some LMS APIs
        # are not capable of decoding these values.
        host = settings.LMS_URL_ROOT.strip('/')
        return '{host}/{path}'.format(host=host, path=path)

    def _retrieve_data_from_lms(self, access_token):
        """
        Retrieves the course name and modes from the LMS.
        """
        headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }

        # Get course name from Course Structure API
        url = self._build_lms_url('api/course_structure/v0/courses/{}/'.format(self.course.id))
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception('Unable to retrieve course name: [{status}] - {body}'.format(status=response.status_code,
                                                                                         body=response.content))

        data = response.json()
        logger.debug(data)
        course_name = data['name']

        # Get modes and pricing from Enrollment API
        url = self._build_lms_url('api/enrollment/v1/course/{}'.format(self.course.id))
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception('Unable to retrieve course modes: [{status}] - {body}'.format(status=response.status_code,
                                                                                          body=response.content))

        data = response.json()
        logger.debug(data)
        modes = data['course_modes']

        return course_name, modes

    def _get_products(self, modes):
        """ Creates/updates course seat products. """
        for mode in modes:
            certificate_type = Course.certificate_type_for_mode(mode['slug'])
            id_verification_required = Course.is_mode_verified(mode['slug'])
            price = mode['min_price']
            expires = mode.get('expiration_datetime')
            expires = dateutil.parser.parse(expires) if expires else None
            self.course.create_or_update_seat(certificate_type, id_verification_required, price, expires=expires)


class Command(BaseCommand):
    help = 'Migrate course modes and pricing from LMS to Oscar.'

    option_list = BaseCommand.option_list + (
        make_option('--access_token',
                    action='store',
                    dest='access_token',
                    default=None,
                    help='OAuth2 access token used to authenticate against the LMS APIs.'),
        make_option('--commit',
                    action='store_true',
                    dest='commit',
                    default=False,
                    help='Save the migrated data to the database. If this is not set, '
                         'migrated data will NOT be saved to the database.'),
    )

    def handle(self, *args, **options):
        course_ids = args
        access_token = options.get('access_token')
        if not access_token:
            logger.error('Courses cannot be migrated if no access token is supplied.')
            return

        for course_id in course_ids:
            course_id = unicode(course_id)
            try:
                with transaction.atomic():
                    migrated_course = MigratedCourse(course_id)
                    migrated_course.load_from_lms(access_token)

                    course = migrated_course.course
                    msg = 'Retrieved info for {0} ({1}):\n'.format(course.id, course.name)

                    for seat in course.seat_products:
                        stock_record = seat.stockrecords.first()
                        data = (seat.attr.certificate_type, seat.attr.id_verification_required,
                                '{0} {1}'.format(stock_record.price_currency, stock_record.price_excl_tax),
                                stock_record.partner_sku, seat.slug, seat.expires)
                        msg += '\t{}\n'.format(data)

                    logger.info(msg)

                    if options.get('commit', False):
                        logger.info('Course [%s] was saved to the database.', migrated_course.course.id)
                        transaction.commit()
                    else:
                        logger.info('Course [%s] was NOT saved to the database.', migrated_course.course.id)
                        raise Exception('Forced rollback.')
            except Exception:  # pylint: disable=broad-except
                logger.exception('Failed to migrate [%s]!', course_id)
