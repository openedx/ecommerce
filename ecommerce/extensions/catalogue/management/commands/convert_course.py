

import logging

from django.core.management import BaseCommand
from django.db import transaction
from oscar.core.loading import get_model
from oscar.test.utils import RequestFactory
from threadlocals.threadlocals import set_thread_variable

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.utils import generate_sku

logger = logging.getLogger(__name__)
Line = get_model('order', 'Line')
Partner = get_model('partner', 'Partner')
StockRecord = get_model('partner', 'StockRecord')


HONOR_TO_AUDIT = 'honor_to_audit'
AUDIT_TO_HONOR = 'audit_to_honor'


class Command(BaseCommand):

    help = 'Convert a list of courses from honor to audit, or vice versa. For use with courses '
    'which already have enrollments.'

    def add_arguments(self, parser):
        parser.add_argument('course_ids', nargs='+', type=str)

        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Save the changes to the database. If this is not set,'
                                 ' migrated data will NOT be saved to the database.')
        parser.add_argument('--partner',
                            action='store',
                            dest='partner',
                            default=None,
                            help='Partner code for the site whose courses should be updated.')
        parser.add_argument('--direction',
                            action='store',
                            dest='direction',
                            choices=(HONOR_TO_AUDIT, AUDIT_TO_HONOR),
                            default=HONOR_TO_AUDIT,
                            help='Which direction to convert the courses. Options are honor_to_audit, or audit_to_'
                                 'honor.')

    def handle(self, *args, **options):
        self.options = options  # pylint: disable=attribute-defined-outside-init
        course_ids = list(map(str, self.options.get('course_ids', [])))

        self.partner = Partner.objects.get(code__iexact=options['partner'])  # pylint: disable=attribute-defined-outside-init
        site = self.partner.default_site
        self._install_current_request(site)

        if options.get('direction') == HONOR_TO_AUDIT:
            conversion = self._convert_honor_to_audit
        else:
            conversion = self._convert_audit_to_honor

        for course_id in course_ids:
            try:
                with transaction.atomic():
                    course = Course.objects.get(id=course_id, partner=self.partner)
                    conversion(course)
                    if self.options.get('commit', False):
                        course.publish_to_lms()
                        logger.info('Course [%s] was saved to the database.', course.id)
                    else:
                        logger.info('Course [%s] was NOT saved to the database.', course.id)
                        raise Exception('Forced rollback.')
            except Exception:  # pylint: disable=broad-except
                logger.exception('Failed to convert [%s]!', course_id)

    def _convert_audit_to_honor(self, course):
        audit_seats = [
            seat for seat in course.seat_products
            if getattr(seat.attr, 'certificate_type', '') == ''
        ]
        if len(audit_seats) != 1:
            logger.error('Course [%s] has [%d] audit seats.', course.id, len(audit_seats))
            raise Exception

        audit_seat = audit_seats[0]

        audit_seat.title = course.get_course_seat_name('honor', False)
        audit_seat.attr.certificate_type = 'honor'
        audit_seat.save()

        stock_record = StockRecord.objects.get(product=audit_seat)
        stock_record.partner_sku = generate_sku(audit_seat, self.partner)
        stock_record.save()

        Line.objects.filter(stockrecord=stock_record).update(partner_sku=stock_record.partner_sku)

    def _convert_honor_to_audit(self, course):
        honor_seats = [
            seat for seat in course.seat_products
            if getattr(seat.attr, 'certificate_type', '') == 'honor'
        ]
        if len(honor_seats) != 1:
            logger.error('Course [%s] has [%d] honor seats.', course.id, len(honor_seats))
            raise Exception

        honor_seat = honor_seats[0]

        honor_seat.title = course.get_course_seat_name('', False)
        honor_seat.attr.certificate_type = ''
        honor_seat.save()

        stock_record = StockRecord.objects.get(product=honor_seat)
        stock_record.partner_sku = generate_sku(honor_seat, self.partner)
        stock_record.save()

        Line.objects.filter(stockrecord=stock_record).update(partner_sku=stock_record.partner_sku)

    def _install_current_request(self, site):
        """Install a thread-local fake request, setting its site. This is
        necessary since publishing to the LMS requires inspecting the
        'current request' and using its attached site to construct LMS
        urls. See ecommerce.core.url_utils for the implementation
        details.

        Arguments:
            site (Site): The site to set.

        Returns:
            None
        """
        request = RequestFactory()
        request.site = site
        set_thread_variable('request', request)
