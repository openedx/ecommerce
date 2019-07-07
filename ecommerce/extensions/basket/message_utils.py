"""
Utilities for sending flash messages via JSON responses.

Since django-oscar uses django flash messages, we have decided to continue to use flash messages for consistency,
even in the new backend-for-frontend APIs.  Only when finally creating the response do we convert from the flash
messages to a list of dicts (usable in a JSON response).

Example list of serialized messages::

    [
        {
            'code': 'some-message-code',
            'message_type': 'error',  # debug|info|success|warning|error
            'developer_message': 'Some message for developers.',
        },
        {
            'message_type': 'info',
            'user_message': 'Some message to users.',
        },
    ]

For messages containing HTML, a message code should be added to the ``safe`` extra_tags.  This message code will
be used to build the message client-side, rather than using potentially unsafe messages from the server.

BEFORE:

    messages.error(self.request, '<strong>My bold error</strong>', extra_tags='safe')

AFTER:

    # For legacy mako template views, the HTML message will still be used and passed as the `user_message`.
    # For new JSON API views, the HTML message will be passed as the `developer_message` and the code will be
    # retrieved from the ``extra_tags``.
    messages.error(self.request, '<strong>My bold error</strong>', extra_tags='safe my-bold-error')

Here is the template that django-oscar provides to display the flash messages:
- https://github.com/django-oscar/django-oscar/blob/ea28ecfcf63565816e1b26ba068943d6f179a6e8
  /src/oscar/templates/oscar/partials/alert_messages.html

"""
from __future__ import absolute_import

import logging

from django.contrib.messages import get_messages
from rest_framework import status

logger = logging.getLogger(__name__)


def get_response_status(messages):
    """
    Returns 400 status if any error messages are found, and 200 otherwise.
    """
    if any(message['message_type'] == 'error' for message in messages):
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_200_OK


def serialize(request):
    """
    Returns Django's flash messages serialized as a list of dicts.
    """
    return [
        _serialize_message(message)
        for message in get_messages(request)
    ]


def _serialize_message(message):
    serialized_message = {
        'message_type': message.level_tag,
    }
    code = _get_message_code(message)
    if code:
        # Message codes are used for HTML-formatted messages that will be constructed client-side.
        # Returning the message as `developer_message` to ensure it doesn't get displayed on the client.
        serialized_message.update({
            'code': code,
            'developer_message': message.message,
        })
    else:
        serialized_message['user_message'] = message.message
    return serialized_message


def _get_message_code(message):
    """
    Returns the message code from the extra_tags of a flash message.

    Arguments:
        message: A flash message

    """
    if not message.extra_tags:
        return None

    extra_tags_list = message.extra_tags.split()

    cleaned_extra_tags = [
        tag
        for tag in extra_tags_list
        # strip extra_tags used as classes by Oscar
        if tag not in ['safe', 'noicon', 'block']
    ]
    if cleaned_extra_tags:
        code = cleaned_extra_tags[0]
        if len(cleaned_extra_tags) > 1:  # pragma: no cover
            logger.warning(
                'Message "%s" has too many unknown extra_tags: [%s]. Only one is expected.'
                ' Using [%s] as the message code.',
                message=message.message,
                cleaned_extra_tags=cleaned_extra_tags,
                code=code,
            )
        return code
    else:
        if 'safe' in extra_tags_list:  # pragma: no cover
            logger.warning(
                'Message "%s" uses the `safe` extra_tag which indicates it includes HTML. An additional'
                'extra_tag is required to provide the message code for the microfrontend client.',
                message.message,
            )
    return None
