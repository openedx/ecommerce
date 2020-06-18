

import json
import logging
import os
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.http import Http404, HttpResponse
from django.views.generic import TemplateView, View
from edx_django_utils.cache import TieredCache
from requests import Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.core.views import StaffOnlyMixin

logger = logging.getLogger(__name__)


class CourseAppView(StaffOnlyMixin, TemplateView):
    template_name = 'courses/course_app.html'

    def get_context_data(self, **kwargs):
        context = super(CourseAppView, self).get_context_data(**kwargs)
        context['admin'] = 'course'

        user = self.request.user
        if user.access_token:
            credit_providers = self.get_credit_providers()
            context['credit_providers'] = json.dumps(credit_providers)
        else:
            logger.warning('User [%s] has no access token, and will not be able to edit courses.', user.username)

        return context

    def get_credit_providers(self):
        """
        Retrieve all credit providers from LMS.

        Results will be sorted alphabetically by display name.
        """
        key = 'credit_providers'
        credit_providers_cache_response = TieredCache.get_cached_response(key)
        if credit_providers_cache_response.is_found:
            return credit_providers_cache_response.value

        try:
            credit_api = self.request.site.siteconfiguration.credit_api_client
            credit_providers = credit_api.providers.get()
            credit_providers.sort(key=lambda provider: provider['display_name'])

            # Update the cache
            TieredCache.set_all_tiers(key, credit_providers, settings.CREDIT_PROVIDER_CACHE_TIMEOUT)
        except (SlumberBaseException, Timeout):
            logger.exception('Failed to retrieve credit providers!')
            credit_providers = []
        return credit_providers


class CourseMigrationView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404

        return super(CourseMigrationView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *_args, **_kwargs):
        course_ids = request.GET.get('course_ids')
        commit = request.GET.get('commit', False)
        commit = commit in ('1', 'true')

        # Capture all output and logging
        out = StringIO()
        err = StringIO()
        log = StringIO()

        root_logger = logging.getLogger()
        log_handler = logging.StreamHandler(log)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_handler.setFormatter(formatter)
        root_logger.addHandler(log_handler)

        try:
            # Log who ran this request
            msg = u'User [%s] requested course migration for [%s]. '
            if commit:
                msg += u'The changes will be committed to the database.'
            else:
                msg += u'The changes will NOT be committed to the database.'

            user = request.user
            logger.info(msg, user.username, course_ids)

            if not course_ids:
                return HttpResponse('No course_ids specified.', status=400)

            course_ids = course_ids.split(',')

            call_command('migrate_course', *course_ids, commit=commit, settings=os.environ['DJANGO_SETTINGS_MODULE'],
                         stdout=out, stderr=err)

            # Format the output for display
            output = u'STDOUT\n{out}\n\nSTDERR\n{err}\n\nLOG\n{log}'.format(out=out.getvalue(), err=err.getvalue(),
                                                                            log=log.getvalue())

            return HttpResponse(output, content_type='text/plain')
        finally:
            # Remove the log capture handler and close all streams
            root_logger.removeHandler(log_handler)
            log.close()
            out.close()
            err.close()


class ConvertCourseView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404

        return super(ConvertCourseView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *_args, **_kwargs):
        course_ids = request.GET.get('course_ids')
        commit = request.GET.get('commit', False)
        commit = commit in ('1', 'true')
        direction = request.GET.get('direction', 'honor_to_audit')
        partner = request.site.siteconfiguration.partner.code

        # Capture all output and logging
        out = StringIO()
        err = StringIO()
        log = StringIO()

        root_logger = logging.getLogger()
        log_handler = logging.StreamHandler(log)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_handler.setFormatter(formatter)
        root_logger.addHandler(log_handler)

        try:
            # Log who ran this request
            msg = u'User [%s] requested conversion of honor seats to audit seats for [%s]. '
            if commit:  # pragma: no cover
                msg += u'The changes will be committed to the database.'
            else:
                msg += u'The changes will NOT be committed to the database.'

            user = request.user
            logger.info(msg, user.username, course_ids)

            if not course_ids:
                return HttpResponse('No course_ids specified.', status=400)

            course_ids = course_ids.split(',')

            call_command(
                'convert_course', *course_ids, commit=commit, partner=partner,
                settings=os.environ['DJANGO_SETTINGS_MODULE'], stdout=out, stderr=err, direction=direction
            )

            # Format the output for display
            output = u'STDOUT\n{out}\n\nSTDERR\n{err}\n\nLOG\n{log}'.format(out=out.getvalue(), err=err.getvalue(),
                                                                            log=log.getvalue())

            return HttpResponse(output, content_type='text/plain')
        finally:
            # Remove the log capture handler and close all streams
            root_logger.removeHandler(log_handler)
            log.close()
            out.close()
            err.close()
