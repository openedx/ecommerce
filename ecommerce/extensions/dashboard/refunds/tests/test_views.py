

from django.urls import reverse

from ecommerce.extensions.refund.status import REFUND
from ecommerce.extensions.refund.tests.factories import RefundFactory
from ecommerce.tests.testcases import TestCase


class RefundViewTestMixin:
    def setUp(self):
        super(RefundViewTestMixin, self).setUp()
        self.user = self.create_user(is_superuser=True, is_staff=True)

    def assert_successful_response(self, response, refunds=None):
        self.assertEqual(response.status_code, 200)

        if refunds:
            self.assertListEqual(list(response.context['refunds']), refunds)

    def test_staff_permissions_required(self):
        """ The view should only be accessible by staff users. """

        # Non-staff users cannot view the page.
        non_staff_user = self.create_user(is_staff=False, is_superuser=False)
        self.client.login(username=non_staff_user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)  # Redirect to logon page

        # Staff users should be able to view the page.
        staff_user = self.create_user(is_staff=True, is_superuser=False)
        self.client.login(username=staff_user.username, password=self.password)
        response = self.client.get(self.path)
        self.assert_successful_response(response)

        # Superusers should be able to view the page, regardless of the staff setting.
        superuser = self.create_user(is_staff=False, is_superuser=True)
        self.client.login(username=superuser.username, password=self.password)
        response = self.client.get(self.path)
        self.assert_successful_response(response)


class RefundListViewTests(RefundViewTestMixin, TestCase):
    path = reverse('dashboard:refunds-list')
    username = 'hackerman'

    def test_filtering(self):
        """ The view should allow filtering by ID, status, and username. """
        refund = RefundFactory()
        open_refund = RefundFactory(status=REFUND.OPEN)
        complete_refund = RefundFactory(status=REFUND.COMPLETE)
        denied_refund = RefundFactory(status=REFUND.DENIED)

        self.client.login(username=self.user.username, password=self.password)

        # Sanity check for an unfiltered query. Completed and denied refunds should be excluded.
        response = self.client.get(self.path)
        self.assert_successful_response(response, [refund, open_refund])

        # ID filtering
        response = self.client.get('{path}?id={id}'.format(path=self.path, id=open_refund.id))
        self.assert_successful_response(response, [open_refund])

        # Single-choice status filtering
        response = self.client.get('{path}?status={status}'.format(path=self.path, status=REFUND.COMPLETE))
        self.assert_successful_response(response, [complete_refund])

        # Multiple-choice status filtering
        response = self.client.get('{path}?status={complete_status}&status={denied_status}'.format(
            path=self.path,
            complete_status=REFUND.COMPLETE,
            denied_status=REFUND.DENIED
        ))
        self.assert_successful_response(response, [complete_refund, denied_refund])

        new_user = self.create_user(username=self.username)
        new_refund = RefundFactory(user=new_user)

        # Username filtering
        response = self.client.get('{path}?username={username}'.format(
            path=self.path,
            username=self.username
        ))
        self.assert_successful_response(response, [new_refund])

        # Validate case-insensitive, starts-with username filtering
        response = self.client.get('{path}?username={username}'.format(
            path=self.path,
            # Cut the configured username in half, then invert the fragment's casing.
            username=self.username[:len(self.username) // 2].swapcase()
        ))
        self.assert_successful_response(response, [new_refund])

    def test_sorting(self):
        """ The view should allow sorting by ID. """
        refunds = [RefundFactory(), RefundFactory(), RefundFactory()]
        self.client.login(username=self.user.username, password=self.password)

        response = self.client.get('{path}?sort=id&dir=asc'.format(path=self.path))
        self.assert_successful_response(response, refunds)

        response = self.client.get('{path}?sort=id&dir=desc'.format(path=self.path))
        self.assert_successful_response(response, list(reversed(refunds)))


class RefundDetailViewTests(RefundViewTestMixin, TestCase):
    def setUp(self):
        super(RefundDetailViewTests, self).setUp()
        self.user = self.create_user(is_superuser=True, is_staff=True)

        refund = RefundFactory()
        self.path = reverse('dashboard:refunds-detail', args=[refund.id])
