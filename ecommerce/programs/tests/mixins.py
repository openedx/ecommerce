import json
from decimal import Decimal

import httpretty
from django.conf import settings

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin


class ProgramTestMixin(CourseCatalogTestMixin):
    def mock_program_detail_endpoint(self, program_uuid):
        """ Mocks the program detail endpoint on the Catalog API.
        Args:
            program_uuid (uuid): UUID of the mocked program.

        Returns:
            dict: Mocked program data.
        """
        courses = []
        for __ in range(1, 5):
            course_runs = []

            for __ in range(1, 4):
                course_run = CourseFactory()
                course_run.create_or_update_seat('audit', False, Decimal(0), self.partner)
                course_run.create_or_update_seat('verified', True, Decimal(100), self.partner)

                course_runs.append({
                    'key': course_run.id,
                    'seats': [{
                        'type': mode_for_seat(seat),
                        'sku': seat.stockrecords.get(partner=self.partner).partner_sku,
                    } for seat in course_run.seat_products]
                })

            courses.append({'course_runs': course_runs, })

        program_uuid = str(program_uuid)
        data = {
            'uuid': program_uuid,
            'title': 'Test Program',
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
            uri='{base}/programs/{uuid}/'.format(base=settings.COURSE_CATALOG_API_URL.strip('/'), uuid=program_uuid),
            body=json.dumps(data),
            content_type='application/json'
        )
        return data
