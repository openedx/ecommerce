"""API endpoint for sending assignment emails to Learners"""
import logging
from datetime import datetime

from ecommerce_worker.sailthru.v1.tasks import send_code_assignment_email
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class AssignmentEmail(APIView):
    """Sends assignment email(s) to Learners."""
    permission_classes = (IsAuthenticated,)

    def get_email_parameters(self, template, template_tokens):
        """
        Injects the provided tokens into the template and returns the learner email, message body and subject
        :param template: email template
        :param template_tokens: tokens to inject into the email template
        :return: learner_email, code, subject, email_body, missing_keys, missing_values, template_key_error
        """
        required_attrs = ('user_email', 'code', 'enrollment_url', 'code_usage_count', 'code_expiration_date')
        missing_keys = [attr for attr in required_attrs if attr not in template_tokens.iterkeys()]
        available_keys = [attr for attr in required_attrs if attr in template_tokens.iterkeys()]
        missing_values = [key for key in available_keys if not template_tokens[key]]
        learner_email = code = subject = email_body = template_key_error = None

        if missing_keys or missing_values:
            return learner_email, code, subject, email_body, missing_keys, missing_values, template_key_error

        learner_email = template_tokens.get('user_email')
        code = template_tokens.get('code')
        enrollment_url = template_tokens.get('enrollment_url')
        code_usage_count = template_tokens.get('code_usage_count')
        expiration_date_iso = template_tokens.get('code_expiration_date')
        code_expiration_date = datetime.strptime(expiration_date_iso, '%Y-%m-%dT%H:%M:%S.%fZ').replace(
            hour=0, minute=0, second=0, microsecond=0)

        subject = 'New edX course assignment'
        try:
            email_body = template.format(
                code_usage_count=code_usage_count,
                user_email=learner_email,
                enrollment_url=enrollment_url,
                code=code,
                code_expiration_date=code_expiration_date
            )
        except KeyError as exc:
            logger.exception('[Code Assignment] Email template key issue: %r', exc)
            template_key_error = str(exc)
            return learner_email, code, subject, email_body, missing_keys, missing_values, template_key_error

        return learner_email, code, subject, email_body, missing_keys, missing_values, template_key_error

    def get_response_status(self, learner_email, code, email_status,
                            missing_keys, missing_values, template_key_error):
        """
        Returns status dict with 'user_email', 'code',
        'status', 'missing_keys', 'missing_values' and 'template_key_error'
        """
        response_status = {
            'user_email': learner_email,
            'code': code,
            'status': email_status,
            'missing_keys': missing_keys,
            'missing_values': missing_values,
            'template_key_error': template_key_error
        }
        return response_status

    def post(self, request):
        """
        POST /enterprise/api/v1/request_codes

        Requires a JSON object of the following format:
       {
            'template': ('Template message with '
                         '{user_email} {code}'
                         ' {enrollment_url} {code_usage_count} {code_expiration_date}'),
            'template_tokens': [
                {
                    'user_email': 'johndoe@unknown.com',
                    'code': 'GIL7RUEOU7VHBH7Q',
                    'enrollment_url': 'http://tempurl.url/enroll',
                    'code_usage_count': '3',
                    'code_expiration_date': '2012-04-23T18:25:43.511Z'
                },
                {
                    'user_email': 'janedoe@unknown.com',
                    'code': 'GIL7RUEOU7VHBH7P',
                    'enrollment_url': 'http://tempurl.url/enroll',
                    'code_usage_count': '3',
                    'code_expiration_date': '2012-04-23T18:25:43.511Z'
                },
            ]
       }
       Returns a JSON object of the following format:

        {u'status': [{u'code': u'GIL7RUEOU7VHBH7Q',
                      u'missing_keys': [],
                      u'missing_values': [],
                      u'status': u'Dispatched',
                      u'template_key_error': None,
                      u'user_email': u'johndoe@unknown.com'},
                     {u'code': u'GIL7RUEOU7VHBH7P',
                      u'missing_keys': [],
                      u'missing_values': [],
                      u'status': u'Dispatched',
                      u'template_key_error': None,
                      u'user_email': u'janedoe@unknown.com'}]
         }

        Keys:
        *template*
            The email template with placeholders that will receive the following tokens
        *user_email*
            Email of the customer who will receive the code.
        *code*
            Code for the user.
        *enrollment_url*
            URL for the user.
        *code_usage_count*
            Number of times the code can be redeemed.
        *code_expiration_date*
            Date till code is valid.
        *status*
            The email send status
        *missing_keys*
            Missing keys in the request
        *missing_values*
            Missing values in the request
        *template_key_error*
            Unknown token in the template
        """

        template = request.data.get('template')
        template_tokens_list = request.data.get('template_tokens')

        if not template or not template_tokens_list:
            return Response({'error': str('Required parameters are missing')}, status=status.HTTP_400_BAD_REQUEST)
        email_status = []
        for template_tokens in template_tokens_list:
            learner_email, code, subject, email_body, missing_keys, missing_values, template_key_error =\
                self.get_email_parameters(template, template_tokens)

            if not missing_keys and not missing_values and not template_key_error:
                try:
                    send_code_assignment_email.delay(learner_email, subject, email_body)
                    response_status = self.get_response_status(
                        learner_email, code, 'Dispatched', missing_keys, missing_values, template_key_error)
                    email_status.append(response_status)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception('[Code Management] Email sending task raised: %r', exc)
                    response_status = self.get_response_status(
                        learner_email, code, 'Failed', missing_keys, missing_values, template_key_error)
                    email_status.append(response_status)
            else:
                response_status = self.get_response_status(
                    learner_email, code, 'Failed', missing_keys, missing_values, template_key_error)
                email_status.append(response_status)
        return Response({'status': email_status}, status=status.HTTP_200_OK)
