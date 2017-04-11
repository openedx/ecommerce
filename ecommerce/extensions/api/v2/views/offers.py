from __future__ import unicode_literals

import hashlib
import json
import logging

from dateutil.parser import parse
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from slumber.exceptions import SlumberBaseException

from ecommerce.courses.models import Course
from ecommerce.extensions.api.serializers import ConditionalOfferSerializer
from ecommerce.extensions.catalogue.models import Catalog

log = logging.getLogger(__name__)

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Condition = get_model('offer', 'Condition')
Benefit = get_model('offer', 'Benefit')
Product = get_model('catalogue', 'Product')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')


class OfferViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAdminUser)
    queryset = ConditionalOffer.objects.filter(offer_type=ConditionalOffer.SITE)
    serializer_class = ConditionalOfferSerializer

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            program_uuid = request.data['program_uuid']
            try:
                program = self._get_program(self.request, program_uuid)
            except (ConnectionError, SlumberBaseException, Timeout):
                log.warning('Unable to retrieve program [%s] from Course Catalog.', program_uuid)
                return Response('Unable to retrieve program.', status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            _range = self.create_range(program)
            benefit = Benefit.objects.create(
                range=_range,
                type=Benefit.PERCENTAGE,
                value=int(request.data['benefit_value'])
            )
            condition = Condition.objects.create(
                range=_range,
                type=Condition.COVERAGE,
                value=_range.catalog.stock_records.count()
            )

            offer = ConditionalOffer.objects.create(
                name='Program: {}'.format(program['title']),
                offer_type=ConditionalOffer.SITE,
                benefit=benefit,
                condition=condition,
                start_datetime=parse(request.data['start_datetime']),
                end_datetime=parse(request.data['end_datetime'])
            )

            return Response(self.serializer_class(offer).data, status=status.HTTP_201_CREATED)

    def _get_program(self, request, program_uuid):
        """Retreives the program data from the Catalog Service."""
        cache_key = hashlib.md5(
            'program_{uuid}'.format(uuid=program_uuid)
        ).hexdigest()
        program = cache.get(cache_key)
        if not program:
            api = request.site.siteconfiguration.course_catalog_api_client
            program = json.loads(api.programs(program_uuid).get())
            cache.set(cache_key, program, settings.PROGRAM_CACHE_TIMEOUT)
        return program

    def create_range(self, program):
        """Create an Oscar Range for the program."""
        stock_records = []
        seat_types = program['applicable_seat_types']
        for course in program['courses']:
            for course_run in course['course_runs']:
                _course = Course.objects.get(id=course_run['key'])
                seat = _course.seat_products.get(
                    attributes__name='certificate_type',
                    attribute_values__value_text__in=seat_types
                )
                stock_records.append(StockRecord.objects.get(product=seat))

        name = 'Program: {}'.format(program['title'])
        catalog = Catalog.objects.create(
            name=name,
            partner=self.request.site.siteconfiguration.partner
        )

        catalog.stock_records.add(*stock_records)
        return Range.objects.create(
            name=name,
            catalog=catalog
        )

    def partial_update(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Handler for the PATCH HTTP method.
        Partially updates the offer depending on request data sent.
        """
        offer = self.get_object()
        program_uuid = request.data.get('program_uuid')
        if program_uuid:
            try:
                program = self._get_program(self.request, program_uuid)
            except (ConnectionError, SlumberBaseException, Timeout):
                log.warning('Unable to retrieve program [%s] from Course Catalog.', program_uuid)
                return Response('Unable to retrieve program.', status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            _range = self.create_range(program)
            offer.benefit.range = _range
            offer.benefit.save()
            offer.condition.range = _range
            offer.condition.save()

        benefit_value = request.data.get('benefit_value')
        if benefit_value:
            offer.benefit.value = benefit_value
            offer.benefit.save()

        start_datetime = request.data.get('start_datetime')
        if start_datetime:
            offer.start_datetime = parse(start_datetime)
            offer.save()

        end_datetime = request.data.get('end_datetime')
        if end_datetime:
            offer.end_datetime = parse(end_datetime)
            offer.save()

        return Response(self.serializer_class(offer).data, status=status.HTTP_200_OK)
