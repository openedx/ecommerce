import logging

from oscar.core.loading import get_class

from ecommerce.extensions.iap.models import IAPProcessorConfiguration

Dispatcher = get_class('communication.utils', 'Dispatcher')
logger = logging.getLogger(__name__)


def send_mail_to_mobile_team_for_change_in_course(course, seats, failure_msg=False):
    recipient = IAPProcessorConfiguration.get_solo().mobile_team_email
    if not recipient:
        msg = "Couldn't mail mobile team for change in %s. No email was specified for mobile team in configurations"
        logger.info(msg, course.name)
        return

    def format_seat(seat):
        seat_template = "Course: {}, Sku: {}, Price: {}"
        stock_record = seat.stockrecords.all()[0]
        result = seat_template.format(
            course.name,
            stock_record.partner_sku,
            stock_record.price,
        )
        return result

    formatted_seats = [format_seat(seat) for seat in seats if seat.stockrecords.all()]

    messages = {
        'subject': 'Course Change Alert for {}'.format(course.name),
        'body': "\n".join(formatted_seats)
    }

    if failure_msg:
        messages['body'] += "\n Failed to update above mobile seats, please do it manually."

    Dispatcher().dispatch_direct_messages(recipient, messages)
    logger.info("Sent change in %s email to mobile team.", course.name)
