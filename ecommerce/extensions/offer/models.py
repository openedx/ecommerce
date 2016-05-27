# noinspection PyUnresolvedReferences
from django.db import models
from oscar.apps.offer.abstract_models import AbstractRange
from threadlocals.threadlocals import get_current_request

from ecommerce.core.url_utils import get_course_catalog_api_client
from ecommerce.coupons.utils import get_seats_from_query


class Range(AbstractRange):
    catalog = models.ForeignKey('catalogue.Catalog', blank=True, null=True, related_name='ranges')
    catalog_query = models.CharField(max_length=255, blank=True, null=True)
    course_seat_types = models.CharField(max_length=255, blank=True, null=True)

    def run_catalog_query(self, product):
        """
        Retrieve the results from running the query contained in catalog_query field.
        """
        request = get_current_request()
        try:
            response = get_course_catalog_api_client(request.site).course_runs.contains.get(
                query=self.catalog_query,
                course_run_ids=product.course_id
            )
        except:  # pylint: disable=bare-except
            raise Exception('Could not contact Course Catalog Service.')
        return response

    def contains_product(self, product):
        if self.catalog_query and self.course_seat_types:
            if product.attr.certificate_type.lower() in self.course_seat_types:  # pylint: disable=unsupported-membership-test
                response = self.run_catalog_query(product)
                # Range can have a catalog query and 'regular' products in it,
                # therefor an OR is used to check for both possibilities.
                return ((response['course_runs'][product.course_id]) or
                        super(Range, self).contains_product(product))  # pylint: disable=bad-super-call
        elif self.catalog:
            return (
                product.id in self.catalog.stock_records.values_list('product', flat=True) or
                super(Range, self).contains_product(product)  # pylint: disable=bad-super-call
            )
        return super(Range, self).contains_product(product)  # pylint: disable=bad-super-call

    contains = contains_product

    def num_products(self):
        return len(self.all_products())

    def all_products(self):
        request = get_current_request()
        if self.catalog_query and self.course_seat_types:
            products = get_seats_from_query(request.site, self.catalog_query, self.course_seat_types)
            return products + list(super(Range, self).all_products())  # pylint: disable=bad-super-call
        if self.catalog:
            catalog_products = [record.product for record in self.catalog.stock_records.all()]
            return catalog_products + list(super(Range, self).all_products())  # pylint: disable=bad-super-call
        return super(Range, self).all_products()  # pylint: disable=bad-super-call

from oscar.apps.offer.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
