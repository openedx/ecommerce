import json
from decimal import Decimal

import httpretty

from ecommerce.core.url_utils import get_lms_enrollment_api_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin


class ProgramTestMixin(DiscoveryTestMixin):
    def mock_program_detail_endpoint(self, program_uuid, discovery_api_url, empty=False, title='Test Program'):
        """ Mocks the program detail endpoint on the Catalog API.
        Args:
            program_uuid (uuid): UUID of the mocked program.

        Returns:
            dict: Mocked program data.
        """
        data = None
        if not empty:
            courses = []
            for i in range(1, 5):
                key = 'course-v1:test-org+course+' + str(i)
                course_runs = []
                for __ in range(1, 4):
                    course_run = CourseFactory()
                    course_run.create_or_update_seat('audit', False, Decimal(0), self.partner)
                    course_run.create_or_update_seat('verified', True, Decimal(100), self.partner)

                    course_runs.append({
                        'key': course_run.id,
                        'seats': [{
                            'type': mode_for_product(seat),
                            'sku': seat.stockrecords.get(partner=self.partner).partner_sku,
                        } for seat in course_run.seat_products]
                    })

                courses.append({'key': key, 'course_runs': course_runs, })

            program_uuid = str(program_uuid)
            data = {
                'uuid': program_uuid,
                'title': title,
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

    def mock_enrollment_api(self, username, enrollments=None, response_code=200):
        """ Mocks enrollment retrieval from LMS
        Returns:
            list: Mocked enrollment data
        """
        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}?user={}'.format(get_lms_enrollment_api_url(), username),
            body=json.dumps([] if enrollments is None else enrollments),
            status=response_code,
            content_type='application/json'
        )
        return enrollments
