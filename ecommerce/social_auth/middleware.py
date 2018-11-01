
import hashlib
import logging
import waffle
from social_django.middleware import SocialAuthExceptionMiddleware
from social_core.exceptions import AuthStateMissing
log = logging.getLogger('ISM')


ENABLE_SESSION_INSPECT = 'enable_session_inspect'


class LogInspectRequestSessionMiddleware(object):
    """Middleware to inspect session for different values
        and see what key and values are being created on Request.
    """

    def process_request(self, request):

        active = waffle.switch_is_active(ENABLE_SESSION_INSPECT)

        request_info = {}
        if active:
            request_logs = ''
            request_logs += '\n=======================================================================\n'
            request_logs += 'Request:' + _get_client_ip(request) + ' Logs for Sessions/Request object'
            request_logs += '\n=======================================================================\n'
            request_info['log_title'] = request_logs

            # Ensuring that this middleware is only hit when both session and
            # user object is already populated by upper levels middlewares
            # for session and user object
            if hasattr(request, 'session') and hasattr(request, 'user'):

                _inspecting_request(request, request_info)
                _inspecting_session(request, request_info)
                _generate_logs(request_info)

            else:
                log.info('No session and authentication middleware called.')


class LogInspectResponseSessionMiddleware(object):
    """Middleware to inspect session for different values
        and see what key and values are being created on Response.
    """

    def process_response(self, request, response):

        active = waffle.switch_is_active(ENABLE_SESSION_INSPECT)

        if active:
            response_info = {}
            response_logs = ''
            response_logs += '\n=======================================================================\n'
            response_logs += 'Response:' + _get_client_ip(request) + ' Logs for Sessions/Request object'
            response_logs += '\n=======================================================================\n'
            response_info['log_title'] = response_logs

            # Ensuring that this middleware is only hit when both session and
            # user object is already populated by lower levels middlewares
            # for session and user object.
            if hasattr(request, 'session') and hasattr(request, 'user'):

                _inspecting_request(request, response_info)
                _inspecting_session(request, response_info)
                _generate_logs(response_info)

            else:
                log.info('No session and authentication middleware called.')

        return response


def _inspecting_request(request, info):
    """
    Logging information from request object
    :param request:
    :return: None
    """

    try:
        if 'REQUEST_METHOD' in request.META and request.META['REQUEST_METHOD']:
            info['request_method'] = request.META['REQUEST_METHOD']
        if 'HTTP_REFERER' in request.META and request.META['HTTP_REFERER']:
            info['http_referer'] = request.META['HTTP_REFERER']
        if 'REMOTE_USER' in request.META and request.META['REMOTE_USER']:
            info['remote_user'] = request.META['HTTP_USER']
        if 'REMOTE_HOST' in request.META and request.META['REMOTE_HOST']:
            info['remote_host'] = request.META['REMOTE_HOST']
        if 'REMOTE_ADDR' in request.META and request.META['REMOTE_ADDR']:
            info['remote_addr'] = request.META['REMOTE_ADDR']

        if request.get_raw_uri():
            info['request_uri'] = request.get_raw_uri()

    except (KeyError, AttributeError) as e:
        log.exception("Error occurred while fetching request details: %s", e.message)


def _inspecting_session(request, info):
    """
    Logging information from session object
    :param request:
    :return: None
    """

    try:
        info['user_email'] = request.user.email if request.user.is_authenticated() else 'None'
        info['session_type'] = 'Authenticated' if request.user.is_authenticated() else 'Unauthenticated'

        if request.session:
            if request.session.session_key:
                info['skey'] = hashlib.sha256(str(request.session.session_key)).hexdigest()
            else:
                info['skey'] = 'Empty Key'
            info['session_object_id'] = str(id(request.session))

            # logging some of details of session cookie name used by django
            from django.conf import settings
            info['session_cookie_name'] = settings.SESSION_COOKIE_NAME
        else:
            log.info('No Session object found')

    except (KeyError, AttributeError) as e:
        log.exception("Error occurred while fetching session details: %s", e.message)


def _generate_logs(info):

    logs = ''

    if 'log_title' in info and info['log_title']:
        logs += info['log_title']

    logs += '\n-----------------Inspecting Request:-------------\n'
    if 'request_method' in info and info['request_method']:
        logs += 'Request Method:' + info['request_method'] + ', '
    if 'http_referer' in info and info['http_referer']:
        logs += 'HTTP Referer:' + info['http_referer'] + ', '
    if 'remote_user' in info and info['remote_user']:
        logs += 'Remote User:' + info['remote_user'] + ', '
    if 'remote_host' in info and info['remote_host']:
        logs += 'Remote Host:' + info['remote_host'] + ', '
    if 'remote_addr' in info and info['remote_addr']:
        logs += 'Remote Address:' + info['remote_addr'] + ', '
    if 'http_host' in info and info['http_host']:
        logs += 'HTTP Host:' + info['http_host'] + ', '
    if 'request_uri' in info and info['request_uri']:
        logs += 'Request URI:' + info['request_uri'] + '\n'

    logs += '-----------------Inspecting Session:----------------\n'
    if 'session_type' in info and info['session_type']:
        logs += 'Session Type:' + info['session_type'] + ', '
    if 'user_email' in info and info['user_email']:
        logs += 'User Email:' + info['user_email'] + ', '
    if 'skey' in info and info['skey']:
        logs += 'SKey:' + info['skey'] + ', '
    if 'session_cookie_name' in info and info['session_cookie_name']:
        logs += 'SCN:' + info['session_cookie_name'] + ', '
    if 'session_object_id' in info and info['session_object_id']:
        logs += 'Session Object Id:' + info['session_object_id'] + '\n'

    log.info(logs)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class LogStateMissingExceptionMiddleware(SocialAuthExceptionMiddleware):
    """
    Middleware for inspecting missing state value in session
    causing AuthStateMissing error to be raised """

    def process_exception(self, request, exception):
        active = waffle.switch_is_active(ENABLE_SESSION_INSPECT)

        if active:
            info = {}
            if isinstance(exception, AuthStateMissing):
                strategy = getattr(request, 'social_strategy', None)
                if strategy and strategy.session:
                    if strategy.session.session_key:
                        info['skey'] = hashlib.sha256(str(strategy.session.session_key)).hexdigest()
                    else:
                        info['skey'] = 'Empty Key'
                info['session_object_id'] = str(id(request.session))

                exception_logs = ''
                exception_logs += '\n=======================================================================\n'
                exception_logs += 'Exception:' + _get_client_ip(request) + ' Logs for StateMissingException'
                exception_logs += '\n=======================================================================\n'

                info['log_title'] = exception_logs

                # logging some of details of session cookie name used by django
                from django.conf import settings
                info['session_cookie_name'] = settings.SESSION_COOKIE_NAME

                _inspecting_request(request, info)
                _generate_logs(info)

        return super(LogStateMissingExceptionMiddleware, self).process_exception(request, exception)
