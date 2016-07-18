import datetime
from django.core.management.base import BaseCommand, CommandError
from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.order.models import Order


class Command(BaseCommand):

    help = """Prints order number of all orders which were paid multiple times between start date and end date.
    Supported action:
        [start_date] [end_date]       'Prints all orders which were paid multiple times in provided time range.'.
    """

    args = "start_date end_date [start_date] [end_date]"

    @staticmethod
    def _get_argument(args, variable_name):
        """
        DRY helper.  Tries to pop topmost value from `args` and raises a CommandError
        with a formatted message in case of failure.  This function mutates `args` in place.
        """
        try:
            return datetime.datetime.strptime(args.pop(0), '%d-%m-%Y')
        except ValueError:
            raise CommandError("{} was not specified or specified correctly in args 'd-m-y'.".format(variable_name))

    def handle(self, *args, **options):
        """
        Main dispatch.
        """
        args = list(args)
        if len(args) < 2:
            raise CommandError("Required arguments `Start Date` and `End Date` are missing.")
        start_date = self._get_argument(args, 'Start Date')
        end_date = self._get_argument(args, 'End Date')
        if start_date >= end_date:
            raise CommandError("Argument `Start Date` must be less than `End Date`.")

        orders = Order.objects.filter(date_placed__range=(start_date, end_date), total_incl_tax__gt=0)
        for order in orders:
            if self.number_of_payments_for_order(order) > 1:
                print str(order.number)

    @staticmethod
    def number_of_payments_for_order(order):
        """
        Gets all PaymentProcessorResponses against the order and finds how many times order was paid.
        Args:
            order: order model object

        Returns: No of payments which have not been refunded (Total Number of Payments - Total Number of refunds)

        """
        number_of_payments = 0
        payment_processor_responses = PaymentProcessorResponse.objects.filter(basket_id=order.basket_id)
        if len(payment_processor_responses) == 1:
            return 1
        for payment_processor_response in payment_processor_responses:
            response = str(payment_processor_response.response)
            if 'paypal' in response:
                # checks if it's a refund response
                if 'update_time' and 'refund' in response:
                    number_of_payments -= 1
                # it's not a update or message response its a payment response
                elif ('update_time' or 'message') not in response:
                    number_of_payments += 1
            else:
                # check if its a cybersource payment response
                if 'sale' in response:
                    number_of_payments += 1
                # check if its a cybersource refund response
                elif 'reconciliation' in response:
                    number_of_payments -= 1
        return number_of_payments
