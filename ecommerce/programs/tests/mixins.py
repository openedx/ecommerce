

import json
from decimal import Decimal

import httpretty

from ecommerce.core.url_utils import get_lms_enrollment_api_url, get_lms_entitlement_api_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_product
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.factories import PartnerFactory


class ProgramTestMixin(DiscoveryTestMixin):
    def mock_program_detail_endpoint(self, program_uuid, discovery_api_url, empty=False, title='Test Program',
                                     include_entitlements=True, status='active'):
        """ Mocks the program detail endpoint on the Catalog API.
        Args:
            program_uuid (uuid): UUID of the mocked program.

        Returns:
            dict: Mocked program data.
        """
        partner = PartnerFactory()
        data = None
        if not empty:
            courses = []
            for i in range(1, 5):
                uuid = '268afbfc-cc1e-415b-a5d8-c58d955bcfc' + str(i)
                entitlement = create_or_update_course_entitlement('verified', 10, partner, uuid, uuid)
                entitlements = []
                if include_entitlements:
                    entitlements.append(
                        {
                            "mode": "verified",
                            "price": "10.00",
                            "currency": "USD",
                            "sku": entitlement.stockrecords.first().partner_sku
                        }
                    )
                key = 'course-v1:test-org+course+' + str(i)
                course_runs = []
                for __ in range(1, 4):
                    course_run = CourseFactory(partner=self.partner)
                    course_run.create_or_update_seat('audit', False, Decimal(0))
                    course_run.create_or_update_seat('verified', True, Decimal(100))

                    course_runs.append({
                        'key': course_run.id,
                        'seats': [{
                            'type': mode_for_product(seat),
                            'sku': seat.stockrecords.get(partner=self.partner).partner_sku,
                        } for seat in course_run.seat_products]
                    })

                courses.append({'key': key, 'uuid': uuid, 'course_runs': course_runs, 'entitlements': entitlements, })

            program_uuid = str(program_uuid)
            data = {
                'uuid': program_uuid,
                'title': title,
                'status': status,
                'type': 'MicroMockers',
                'courses': courses,
                'applicable_seat_types': [
                    'verified',
                    'professional',
                    'credit'
                ],
            }
        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{base}/programs/{uuid}/'.format(
                base=discovery_api_url.strip('/'),
                uuid=program_uuid
            ),
            body=json.dumps(data),
            content_type='application/json'
        )
        return data

    def mock_user_data(self, username, mocked_api='enrollments', owned_products=None, response_code=200):
        """ Mocks user ownership data retrieval from LMS
        Returns:
            list: Mocked entitlement or enrollment data
        """
        self.mock_access_token_response()
        if mocked_api == 'enrollments':
            api_url = get_lms_enrollment_api_url()
        else:
            api_url = get_lms_entitlement_api_url() + 'entitlements/'
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}?user={}'.format(api_url, username),
            body=json.dumps([] if owned_products is None else owned_products),
            status=response_code,
            content_type='application/json'
        )
        return owned_products
