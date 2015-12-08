from __future__ import unicode_literals

import logging
from optparse import make_option

from django.core.management import BaseCommand
from django.db import transaction
from oscar.core.loading import get_model

from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)
Partner = get_model('partner', 'Partner')


# TODO If this is not immediately deleted after we convert courses, make sure this is updated to support
# multi-tenancy.
class Command(BaseCommand):
    help = 'Replace an existing honor seat with an audit seat for one, or more, courses.'

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
                    help='Save the changes to the database. If this is not set, '
                         'migrated data will NOT be saved to the database.'),
    )

    def handle(self, *args, **options):
        course_ids = args
        access_token = options.get('access_token')

        if not access_token:
            logger.error('Courses cannot be migrated if no access token is supplied.')
            return

        partner = Partner.objects.get(code='edx')

        for course_id in course_ids:
            course_id = unicode(course_id)

            # Retrieve the course
            course = Course.objects.get(id=course_id)

            try:
                with transaction.atomic():

                    # Delete the honor seat(s)
                    honor_seats = [seat for seat in course.seat_products if
                                   getattr(seat.attr, 'certificate_type', '') == 'honor']
                    for seat in honor_seats:
                        seat.delete()

                    # Create an audit seat
                    course.create_or_update_seat('', False, 0, partner)

                    if options.get('commit', False):
                        logger.info('Course [%s] was saved to the database.', course.id)
                        course.publish_to_lms(access_token=access_token)
                    else:
                        logger.info('Course [%s] was NOT saved to the database.', course.id)
                        raise Exception('Forced rollback.')
            except Exception:  # pylint: disable=broad-except
                logger.exception('Failed to convert [%s]!', course_id)
