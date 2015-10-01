"""HTTP endpoints for interacting with courses."""
from rest_framework import status
from rest_framework.decorators import detail_route
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
import waffle

from ecommerce.core.constants import COURSE_ID_REGEX
from ecommerce.courses.models import Course
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet
from ecommerce.extensions.api import serializers


class CourseViewSet(NonDestroyableModelViewSet):
    lookup_value_regex = COURSE_ID_REGEX
    queryset = Course.objects.all()
    serializer_class = serializers.CourseSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_serializer_context(self):
        context = super(CourseViewSet, self).get_serializer_context()
        context['include_products'] = bool(self.request.GET.get('include_products', False))
        return context

    @detail_route(methods=['post'])
    def publish(self, request, pk=None):  # pylint: disable=unused-argument
        """ Publish the course to LMS. """
        course = self.get_object()
        published = False
        msg = 'Course [{course_id}] was not published to LMS ' \
              'because the switch [publish_course_modes_to_lms] is disabled.'

        if waffle.switch_is_active('publish_course_modes_to_lms'):
            access_token = getattr(request.user, 'access_token', None)
            published = course.publish_to_lms(access_token=access_token)
            if published:
                msg = 'Course [{course_id}] was successfully published to LMS.'
            else:
                msg = 'An error occurred while publishing [{course_id}] to LMS.'

        return Response({'status': msg.format(course_id=course.id)},
                        status=status.HTTP_200_OK if published else status.HTTP_500_INTERNAL_SERVER_ERROR)
