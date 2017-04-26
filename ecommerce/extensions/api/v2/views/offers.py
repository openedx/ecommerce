from __future__ import unicode_literals

import logging

from dateutil.parser import parse
from django.db import transaction
from oscar.core.loading import get_model
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.api.serializers import ConditionalOfferSerializer

log = logging.getLogger(__name__)

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Condition = get_model('offer', 'Condition')
Benefit = get_model('offer', 'Benefit')
Range = get_model('offer', 'Range')

PROGRAM_NAME_PATTERN = 'Program_{}'


class OfferViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAdminUser)
    queryset = ConditionalOffer.objects.filter(offer_type=ConditionalOffer.SITE)
    serializer_class = ConditionalOfferSerializer

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            program_uuid = request.data['program_uuid']
            _range = Range.objects.create(
                name=PROGRAM_NAME_PATTERN.format(program_uuid),
                program_uuid=program_uuid
            )
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
                name=PROGRAM_NAME_PATTERN.format(program_uuid),
                offer_type=ConditionalOffer.SITE,
                benefit=benefit,
                condition=condition,
                start_datetime=parse(request.data['start_datetime']),
                end_datetime=parse(request.data['end_datetime'])
            )

            return Response(self.serializer_class(offer).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Handler for the PATCH HTTP method.
        Partially updates the offer depending on request data sent.
        """
        offer = self.get_object()
        program_uuid = request.data.get('program_uuid')
        if program_uuid:
            _range = offer.benefit.range
            _range.name = PROGRAM_NAME_PATTERN.format(program_uuid)
            _range.program_uuid = program_uuid
            _range.save()
            offer.name = PROGRAM_NAME_PATTERN.format(program_uuid)
            offer.save()

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
