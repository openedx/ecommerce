"""HTTP endpoint for verifying the health of the ecommerce front-end."""
import logging

import requests
from requests.exceptions import RequestException
from rest_framework import status
from django.conf import settings
from django.db import connection, DatabaseError
from django.http import JsonResponse

from ecommerce.health.constants import Status, UnavailabilityMessage


logger = logging.getLogger(__name__)

LMS_HEALTH_PAGE = getattr(settings, 'LMS_HEARTBEAT_URL')


def health(_):
    """Allows a load balancer to verify that the ecommerce front-end service is up.

    Checks the status of the database connection and the LMS, the two services
    on which the ecommerce front-end currently depends.

    Returns:
        HttpResponse: 200 if the ecommerce front-end is available, with JSON data
            indicating the health of each required service
        HttpResponse: 503 if the ecommerce front-end is unavailable, with JSON data
            indicating the health of each required service

    Example:
        >>> response = requests.get('https://ecommerce.edx.org/health')
        >>> response.status_code
        200
        >>> response.content
        '{"overall_status": "OK", "detailed_status": {"database_status": "OK", "lms_status": "OK"}}'
    """
    overall_status = database_status = lms_status = Status.UNAVAILABLE

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        database_status = Status.OK
    except DatabaseError:

        database_status = Status.UNAVAILABLE

    try:
        response = requests.get(LMS_HEALTH_PAGE)

        if response.status_code == status.HTTP_200_OK:
            lms_status = Status.OK
        else:
            logger.critical(UnavailabilityMessage.LMS)
            lms_status = Status.UNAVAILABLE
    except RequestException:
        logger.critical(UnavailabilityMessage.LMS)
        lms_status = Status.UNAVAILABLE

    overall_status = Status.OK if (database_status == lms_status == Status.OK) else Status.UNAVAILABLE

    data = {
        'overall_status': overall_status,
        'detailed_status': {
            'database_status': database_status,
            'lms_status': lms_status,
        },
    }

    if overall_status == Status.OK:
        return JsonResponse(data)
    else:
        return JsonResponse(data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
