from django.conf import settings
from django.core import mail
from django.test import TestCase
import httpretty
from oscar.test import factories
from oscar.test.newfactories import BasketFactory, UserFactory

from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.checkout.signals import send_course_purchase_email
from ecommerce.settings import get_lms_url
from ecommerce.tests.mixins import PartnerMixin


class SignalTests(CourseCatalogTestMixin, PartnerMixin, TestCase):
    @httpretty.activate
    def test_post_checkout_callback(self):
        """
        When the post_checkout signal is emitted, the receiver should attempt
        to fulfill the newly-placed order and send receipt email.
        """
        httpretty.register_uri(
            httpretty.GET, get_lms_url('api/credit/v1/providers/ASU'),
            body='{"display_name": "Hogwarts"}',
            content_type="application/json"
        )
        toggle_switch('ENABLE_NOTIFICATIONS', True)
        user = UserFactory()
        course = Course.objects.create(id='edX/DemoX/Demo_Course', name='Demo Course')
        partner = self.create_partner('edx')
        seat = course.create_or_update_seat('credit', False, 50, partner, 'ASU', None, 2)

        basket = BasketFactory()
        basket.add_product(seat, 1)
        order = factories.create_order(number=1, basket=basket, user=user)
        send_course_purchase_email(None, order=order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Order Receipt')
        self.assertEqual(
            mail.outbox[0].body,
            '\nReceipt Confirmation for: {course_name}'
            '\n\nHi {full_name},\n\n'
            'Thank you for purchasing {credit_hour} credit hours from {provider_name} for {course_name}.'
            ' The charge below will appear on your next credit or debit card statement with a '
            'company name of {platform_name}.\n\nYou can see the status the status of your credit request or '
            'complete the credit request process on your {platform_name} dashboard\nTo browse other '
            'credit-eligible courses visit the edX website. More courses are added all the time.\n\n'
            'Thank you and congratulation on your achievement. We hope you enjoy the course!\n\n'
            'To view receipt please visit the link below'
            '\n\n{receipt_url}\n\n'
            '{platform_name} team\n\nThe edX team\n'.format(
                course_name=order.lines.first().product.title,
                full_name=user.get_full_name(),
                credit_hour=2,
                provider_name='Hogwarts',
                platform_name=settings.PLATFORM_NAME,
                receipt_url=get_lms_url('/commerce/checkout/receipt/?basket_id={}'.format(order.basket.id))
            )
        )
