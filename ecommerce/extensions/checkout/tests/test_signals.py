import json

from django.conf import settings
from django.core import mail
import httpretty
from oscar.test import factories
from oscar.test.newfactories import BasketFactory
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.checkout.signals import send_course_purchase_email
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.checkout.signals'


class SignalTests(CourseCatalogTestMixin, TestCase):

    def setUp(self):
        super(SignalTests, self).setUp()
        self.user = self.create_user()
        self.request.user = self.user
        self.toggle_ecommerce_receipt_page(True)
        toggle_switch('ENABLE_NOTIFICATIONS', True)

    def prepare_order(self, seat_type, credit_provider_id=None):
        """
        Prepares order for a post-checkout test.

        Args:
            seat_type (str): Course seat type
            credit_provider_id (str): Credit provider associated with the course seat.

        Returns:
            Order
        """
        course = CourseFactory()
        seat = course.create_or_update_seat(seat_type, False, 50, self.partner, credit_provider_id, None, 2)
        basket = BasketFactory(site=self.site)
        basket.add_product(seat, 1)
        order = factories.create_order(basket=basket, user=self.user)
        return order

    @httpretty.activate
    def test_post_checkout_callback(self):
        """
        When the post_checkout signal is emitted, the receiver should attempt
        to fulfill the newly-placed order and send receipt email.
        """
        credit_provider_id = 'HGW'
        credit_provider_name = 'Hogwarts'
        body = {'display_name': credit_provider_name}
        httpretty.register_uri(
            httpretty.GET,
            self.site.siteconfiguration.build_lms_url(
                'api/credit/v1/providers/{credit_provider_id}/'.format(credit_provider_id=credit_provider_id)
            ),
            body=json.dumps(body),
            content_type='application/json'
        )

        order = self.prepare_order('credit', credit_provider_id=credit_provider_id)
        self.mock_access_token_response()
        send_course_purchase_email(None, user=self.user, order=order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, order.site.siteconfiguration.from_email)
        self.assertEqual(mail.outbox[0].subject, 'Order Receipt')
        self.assertEqual(
            mail.outbox[0].body,
            '\nPayment confirmation for: {course_title}'
            '\n\nDear {full_name},'
            '\n\nThank you for purchasing {credit_hours} credit hours from {credit_provider_name} for {course_title}. '
            'A charge will appear on your credit or debit card statement with a company name of "{platform_name}".'
            '\n\nTo receive your course credit, you must also request credit at the {credit_provider_name} website. '
            'For a link to request credit from {credit_provider_name}, or to see the status of your credit request, '
            'go to your {platform_name} dashboard.'
            '\n\nTo explore other credit-eligible courses, visit the {platform_name} website. '
            'We add new courses frequently!'
            '\n\nTo view your payment information, visit the following website.'
            '\n{receipt_url}'
            '\n\nThank you. We hope you enjoyed your course!'
            '\nThe {platform_name} team'
            '\n\nYou received this message because you purchased credit hours for {course_title}, '
            'an {platform_name} course.\n'.format(
                course_title=order.lines.first().product.title,
                full_name=self.user.get_full_name(),
                credit_hours=2,
                credit_provider_name=credit_provider_name,
                platform_name=self.site.name,
                receipt_url=self.site.siteconfiguration.build_ecommerce_url(
                    '{}?order_number={}'.format(settings.RECEIPT_PAGE_PATH, order.number)
                )
            )
        )

    def test_post_checkout_callback_no_credit_provider(self):
        order = self.prepare_order('verified')
        with LogCapture(LOGGER_NAME) as l:
            send_course_purchase_email(None, user=self.user, order=order)
            l.check(
                (
                    LOGGER_NAME,
                    'ERROR',
                    'Failed to send credit receipt notification. Credit seat product [{}] has no provider.'.format(
                        order.lines.first().product.id
                    )
                )
            )
