

import logging

from oscar.core.loading import get_class, get_model
from premailer import transform

from ecommerce.extensions.analytics.utils import parse_tracking_context

log = logging.getLogger(__name__)
CommunicationEventType = get_model('customer', 'CommunicationEventType')
Dispatcher = get_class('customer.utils', 'Dispatcher')


def send_notification(user, commtype_code, context, site, recipient=None):
    """Send different notification mail to the user based on the triggering event.

    Args:
    user(obj): 'User' object to whom email is to send
    commtype_code(str): Communication type code
    context(dict): context to be used in the mail
    recipient(str): Email which overrides user.email when set

    """

    tracking_id, client_id, ip = parse_tracking_context(user, usage='notification')

    tracking_pixel = 'https://www.google-analytics.com/collect?v=1&t=event&ec=email&ea=open&tid={tracking_id}' \
                     '&cid={client_id}&uip={ip}'.format(tracking_id=tracking_id, client_id=client_id, ip=ip)
    full_name = user.get_full_name()
    context.update({
        'full_name': full_name,
        'site_domain': site.domain,
        'platform_name': site.name,
        'tracking_pixel': tracking_pixel,
    })

    try:
        event_type = CommunicationEventType.objects.get(code=commtype_code)
    except CommunicationEventType.DoesNotExist:
        try:
            messages = CommunicationEventType.objects.get_and_render(commtype_code, context)
        except Exception:  # pylint: disable=broad-except
            log.error('Unable to locate a DB entry or templates for communication type [%s]. '
                      'No notification has been sent.', commtype_code)
            return
    else:
        messages = event_type.get_messages(context)

    if messages and (messages['body'] or messages['html']):
        messages['html'] = transform(messages['html'])
        Dispatcher().dispatch_user_messages(user, messages, site, recipient)
