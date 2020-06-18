

import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from oscar.core.loading import get_model
from waffle.models import Flag

from ecommerce.courses.models import Course

Partner = get_model('partner', 'Partner')


class Command(BaseCommand):
    help = 'Create demo course, its seats and publishes it to LMS. This should only be run in development environments!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner',
            action='store',
            dest='partner_code',
            type=str,
            required=True,
            help='Code for the partner with which the course should be associated'
        )
        parser.add_argument(
            '--course-id',
            action='store',
            dest='course_id',
            type=str,
            default='course-v1:edX+DemoX+Demo_Course',
            help='ID of the course to be created/updated. Defaults to course-v1:edX+DemoX+Demo_Course.'
        )
        parser.add_argument(
            '--course-title',
            action='store',
            dest='course_title',
            type=str,
            default='edX Demonstration Course',
            help='Title of the course to be created/updated. Defaults to edX Demonstration Course.'
        )
        parser.add_argument(
            '--price',
            action='store',
            dest='price',
            type=int,
            default=149,
            help='Cost of the verified seat. Defaults to 149'
        )

    def handle(self, *args, **options):
        course_id = options['course_id']
        course_title = options['course_title']
        price = options['price']
        partner = Partner.objects.get(short_code=options['partner_code'])
        one_year = datetime.timedelta(days=365)
        expires = timezone.now() + one_year

        # Enable client-side checkout
        # TODO Use the management command in edx/devstack once https://github.com/jsocol/django-waffle/issues/199
        # is resolved.
        Flag.objects.update_or_create(name='enable_client_side_checkout', defaults={'everyone': True})

        # Create the course
        course, __ = Course.objects.update_or_create(id=course_id, partner=partner, defaults={
            'name': course_title,
            'verification_deadline': expires + one_year,
        })

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
            'verified', True, price, expires=expires, create_enrollment_code=True, sku=verified_sku
        )
        self.stdout.write(
            self.style.SUCCESS('Created audit and verified seats for [{course_id}]'.format(course_id=course_id))
        )

        # Publish the data to the LMS
        if course.publish_to_lms():
            msg = 'An error occurred while attempting to publish [{course_id}] to LMS'.format(course_id=course_id)
            self.stderr.write(self.style.ERROR(msg))
        else:
            msg = 'Published course modes for [{course_id}] to LMS'.format(course_id=course_id)
            self.stdout.write(self.style.SUCCESS(msg))
