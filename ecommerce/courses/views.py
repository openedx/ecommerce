from StringIO import StringIO
import logging

from django.core.management import call_command
from django.http import Http404, HttpResponse
from django.views.generic import View

logger = logging.getLogger(__name__)


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

        # Log who ran this request
        msg = 'User [%s] requested course migration for [%s]. '
        if commit:
            msg += 'The changes will be committed to the database.'
        else:
            msg += 'The changes will NOT be committed to the database.'

        logger.info(msg, request.user.username, course_ids)

        if not course_ids:
            return HttpResponse('No course_ids specified.', status=400)

        course_ids = course_ids.split(',')

        call_command('migrate_course', *course_ids, commit=commit, stdout=out, stderr=err)

        # Format the output for display
        output = 'STDOUT\n{out}\n\nSTDERR\n{err}\n\nLOG\n{log}'.format(out=out.getvalue(), err=err.getvalue(),
                                                                       log=log.getvalue())

        # Remove the log capture handler
        root_logger.removeHandler(log_handler)

        return HttpResponse(output, content_type='text/plain')
