"""Tests for the sync_mobile_seats_price_and_expiry_with_web command"""
from datetime import datetime

from django.core.management import call_command

from ecommerce.extensions.iap.management.commands.tests.testutils import BaseIAPManagementCommandTests


class SyncMobileSeatsTests(BaseIAPManagementCommandTests):
    """
    Tests for the sync_mobile_seats_price_and_expiry_with_web command.
    """
    def setUp(self):
        super().setUp()
        self.command = 'sync_mobile_seats_price_and_expiry_with_web'
        self.course_with_all_seats = self.create_course_and_seats(create_mobile_seats=True, create_web_seat=True)
        self.course_with_web_seat_only = self.create_course_and_seats(create_mobile_seats=False, create_web_seat=True)
        self.course_with_audit_seat = self.create_course_and_seats(create_mobile_seats=False, create_web_seat=False)
        self.course_with_unsync_seats = self.create_course_and_seats(create_mobile_seats=True, create_web_seat=True)
        self.course_with_unsync_seats2 = self.create_course_and_seats(create_mobile_seats=True, create_web_seat=True)
        mobile_seats = self.get_mobile_seats_for_course(self.course_with_unsync_seats)
        mobile_seats = list(mobile_seats) + list(self.get_mobile_seats_for_course(self.course_with_unsync_seats2))

        for mobile_seat in mobile_seats:
            mobile_seat.expiry = datetime.now()
            mobile_seat.save()

            stockrecord = mobile_seat.stockrecords.all()[0]
            stockrecord.price_excl_tax += 10
            stockrecord.save()

    def test_sync_mobile_seat(self):
        web_seat = self.get_web_seat_for_course(self.course_with_unsync_seats)
        web_seat_expiry = web_seat.expires
        web_seat_price = web_seat.stockrecords.all()[0].price_excl_tax

        web_seat = self.get_web_seat_for_course(self.course_with_unsync_seats2)
        web_seat_expiry2 = web_seat.expires
        web_seat_price2 = web_seat.stockrecords.all()[0].price_excl_tax

        call_command(self.command)
        self.verify_course_seats_update(self.course_with_unsync_seats, web_seat_expiry, web_seat_price)
        self.verify_course_seats_update(self.course_with_unsync_seats2, web_seat_expiry2, web_seat_price2)

    def verify_course_seats_update(self, course, expiry, price):
        mobile_seats = self.get_mobile_seats_for_course(course)
        for mobile_seat in mobile_seats:
            assert mobile_seat.expires == expiry
            assert mobile_seat.stockrecords.all()[0].price_excl_tax == price
