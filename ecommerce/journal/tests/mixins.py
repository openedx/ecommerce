import json

from django.urls import reverse
from oscar.core.loading import get_model

Product = get_model('catalogue', 'Product')

DEFAULT_JOURNALS = [
    {
        "uuid": "73fdd362-ec19-4147-93cf-0a9648b3ffde",
        "partner": "edx",
        "organization": "edx",
        "title": "dummy-title",
        "price": "2.33",
        "currency": "GBP",
        "sku": "4F0B1GZ",
        "status": "active"
    },
    {
        "uuid": "4b2d95f9-5955-475c-9521-eeaff5861a04",
        "partner": "edx",
        "organization": "edx",
        "title": "dummy-title1",
        "price": "2.13",
        "currency": "GBP",
        "sku": "3FPB1GZ",
        "status": "active"
    },
]

DEFAULT_COURSE = [
    {
        "key": "ABC+ABC101",
        "uuid": "573a02ab-5fbe-480e-8fcc-c97e8adfcefa",
        "title": "Matt edX test course",
        "course_runs": [
            {
                "key": "course-v1:ABC+ABC101+2015_T1",
                "uuid": "9b070b33-2669-46e1-ab13-ae2f157a2bb0",
                "title": "Matt edX test course",
                "seats": [
                    {
                        "type": "credit",
                        "price": "10.00",
                        "currency": "USD",
                        "upgrade_deadline": "2016-06-27T00:00:00Z",
                        "credit_provider": "asu",
                        "credit_hours": 2,
                        "sku": "unit01",
                        "bulk_sku": None
                    },
                    {
                        "type": "honor",
                        "price": "0.00",
                        "currency": "USD",
                        "upgrade_deadline": None,
                        "credit_provider": None,
                        "credit_hours": None,
                        "sku": "unit02",
                        "bulk_sku": None
                    },
                    {
                        "type": "verified",
                        "price": "10.00",
                        "currency": "USD",
                        "upgrade_deadline": "2016-06-27T00:00:00Z",
                        "credit_provider": None,
                        "credit_hours": None,
                        "sku": "unit03",
                        "bulk_sku": "2DF467D"
                    }
                ],
                "start": "2015-01-08T00:00:00Z",
                "end": "2016-12-30T00:00:00Z",
                "enrollment_start": "2016-01-01T00:00:00Z",
                "enrollment_end": None,
                "pacing_type": "self_paced",
                "type": "credit",
                "status": "unpublished",
                "course": "ABC+ABC101",
                "full_description": None,
                "announcement": None,
                "availability": "Archived",
                "reporting_type": "test",
            }
        ]
    }
]

EXTRA_COURSE = [
    {
        "key": "DEF+DEF101",
        "uuid": "0e8cbcaa-075b-4e38-a8c3-1876464c2926",
        "title": "Second edX test course",
        "course_runs": [
            {
                "key": "course-v1:DEF+DEF101+2016_T2",
                "uuid": "4786e7be-2390-4332-a20e-e24895c38109",
                "title": "Second edX test course",
                "seats": [
                    {
                        "type": "credit",
                        "price": "10.00",
                        "currency": "USD",
                        "upgrade_deadline": "2016-06-27T00:00:00Z",
                        "credit_provider": "asu",
                        "credit_hours": 2,
                        "sku": "sku01",
                        "bulk_sku": None
                    },
                    {
                        "type": "honor",
                        "price": "0.00",
                        "currency": "USD",
                        "upgrade_deadline": None,
                        "credit_provider": None,
                        "credit_hours": None,
                        "sku": "sku02",
                        "bulk_sku": None
                    },
                    {
                        "type": "verified",
                        "price": "10.00",
                        "currency": "USD",
                        "upgrade_deadline": "2016-06-27T00:00:00Z",
                        "credit_provider": None,
                        "credit_hours": None,
                        "sku": "sku03",
                        "bulk_sku": "2DF467D"
                    }
                ],
                "start": "2015-01-08T00:00:00Z",
                "end": "2016-12-30T00:00:00Z",
                "enrollment_start": "2016-01-01T00:00:00Z",
                "enrollment_end": None,
                "pacing_type": "self_paced",
                "type": "credit",
                "status": "unpublished",
                "course": "DEF+DEF101",
                "full_description": None,
                "announcement": None,
                "availability": "Archived",
                "reporting_type": "test",
            }
        ]
    }
]


class JournalMixin(object):
    """ Mixin for preparing data for Journal Testing. """

    value_text = "dummy-text"
    path = reverse("journal:api:v1:journal-list")

    def create_product(self, client, data=None):
        """ Creates Journal product """
        data = data if data else self.get_data_for_create()
        client.post(
            self.path,
            json.dumps(data),
            "application/json"
        )
        return Product.objects.first()

    def get_data_for_create(self, sku=None):
        """ Returns the default data to create the Journal Product """
        return {
            'attribute_values': [
                {'code': 'weight', 'name': 'weight', 'value': self.value_text}
            ],
            'stockrecords': [
                {
                    'partner': 'edx',
                    'partner_sku': sku if sku else 'unit02',
                    'price_excl_tax': '9.99',
                    'price_currency': 'GBP'
                }
            ],
            'product_class': 'Journal',
            'title': 'dummy-product-title',
            'expires': None,
            'id': None,
            'structure': 'standalone'
        }

    def get_product(self, client, value_text=None):
        """ Returns the Journal Product """
        value_text = value_text if value_text else self.value_text
        path = reverse(
            'journal:api:v1:journal-detail',
            kwargs={'attribute_values__value_text': value_text}
        )

        return json.loads(
            client.get(path).content
        )

    def get_mocked_discovery_journal_bundle(
            self,
            empty_journals=False,
            empty_courses=False,
            applicable_seat_types=None,
            multiple_courses=False
    ):
        courses = []
        if not empty_courses:
            courses = DEFAULT_COURSE
            if multiple_courses:
                courses = DEFAULT_COURSE + EXTRA_COURSE

        return {
            "uuid": "1918b738-979f-42cb-bde0-13335366fa86",
            "title": "dummy-title",
            "partner": "edx",
            "journals": [] if empty_journals else DEFAULT_JOURNALS,
            "courses": courses,
            "applicable_seat_types": applicable_seat_types if applicable_seat_types else ["credit", "honor", "verified"]
        }
