# noinspection PyUnresolvedReferences
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.db import models
from oscar.apps.offer.abstract_models import AbstractConditionalOffer, AbstractRange
from threadlocals.threadlocals import get_current_request

from ecommerce.coupons.utils import get_seats_from_query


class ConditionalOffer(AbstractConditionalOffer):
    email_domains = models.CharField(max_length=255, blank=True, null=True)

    def is_email_valid(self, email):
        """
        Check if the email is within the email_domains if email_domains are set,
        else return True.
        """
        domain = email.split('@')[1]
        return domain in self.email_domains if self.email_domains else True  # pylint: disable=unsupported-membership-test

    def is_condition_satisfied(self, basket):
        """
        In addition to Oscar's check to see if the condition is satisfied,
        a check for if basket owners email domain is within the allowed email domains.
        """
        if not self.is_email_valid(basket.owner.email):
            return False
        return super(ConditionalOffer, self).is_condition_satisfied(basket)  # pylint: disable=bad-super-call


class Range(AbstractRange):
    UPDATABLE_RANGE_FIELDS = [
        'catalog_query',
        'course_seat_types',
    ]
    catalog = models.ForeignKey('catalogue.Catalog', blank=True, null=True, related_name='ranges')
    catalog_query = models.CharField(max_length=255, blank=True, null=True)
    course_seat_types = models.CharField(max_length=255, blank=True, null=True)

    def run_catalog_query(self, product):
        """
        Retrieve the results from running the query contained in catalog_query field.
        """
        cache_key = 'catalog_query_contains [{}] [{}]'.format(self.catalog_query, product.course_id)
        cache_hash = hashlib.md5(cache_key).hexdigest()
        response = cache.get(cache_hash)
        if not response:  # pragma: no cover
            request = get_current_request()
            try:
                response = request.site.siteconfiguration.course_catalog_api_client.course_runs.contains.get(
                    query=self.catalog_query,
                    course_run_ids=product.course_id,
                    partner=request.site.siteconfiguration.partner.short_code
                )
                cache.set(cache_hash, response, settings.COURSES_API_CACHE_TIMEOUT)
            except:  # pylint: disable=bare-except
                raise Exception('Could not contact Course Catalog Service.')

        return response

    def contains_product(self, product):
        """
        Assert if the range contains the product.
        """
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
