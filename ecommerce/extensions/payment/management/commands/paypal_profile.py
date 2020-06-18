

import json
import logging

import paypalrestsdk
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError
from paypalrestsdk import WebProfile  # pylint: disable=ungrouped-imports

from ecommerce.extensions.payment.models import PaypalWebProfile

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """Manage PayPal Web Experience Profiles.

    Supported actions:
        list                Print a JSON-formatted list of existing web profiles.
        create [json]       Create a new profile using the specified JSON string.
        show [id]           Print the contents of an existing web profile.
        update [id] [json]  Update an existing profile using the specified JSON string.
        delete [id]         Delete an existing profile. (Use -d to automatically disable when deleting.)
        enable [id]         Enable the web profile in this Django application (send it in PayPal API calls).
        disable [id]        Disable the web profile in this Django application (don't send in PayPal API calls).

    The 'enable' and 'disable' actions are idempotent so it is safe to run them repeatedly in the same environment.
    """
    args = "action partner [id] [json]"

    PAYPAL_CONFIG_KEY = "paypal"

    def add_arguments(self, parser):
        parser.add_argument('--partner',
                            help='Short code for the specified partner.')
        parser.add_argument('--action',
                            help=self.help)
        parser.add_argument('--profile_id',
                            help='Paypal account web profile id.')
        parser.add_argument('--json',
                            help='JSON string for Paypal web profile.')

    def print_json(self, data):
        self.stdout.write(json.dumps(data, indent=1, ensure_ascii=True))

    def handle(self, *args, **options):
        """
        Main dispatch.
        """

        partner = options.get('partner')
        action = options.get('action')

        if not partner or not action:
            raise CommandError('Required arguments `partner` and `action` are missing')

        try:
            paypal_configuration = settings.PAYMENT_PROCESSOR_CONFIG[partner.lower()][self.PAYPAL_CONFIG_KEY.lower()]
        except KeyError:
            raise CommandError(
                "Payment Processor configuration for partner `{0}` does not contain PayPal settings".format(partner)
            )

        # Initialize the PayPal REST SDK
        paypalrestsdk.configure({
            'mode': paypal_configuration['mode'],
            'client_id': paypal_configuration['client_id'],
            'client_secret': paypal_configuration['client_secret']
        })

        try:
            handler = getattr(self, 'handle_{}'.format(action))
        except IndexError:
            raise CommandError("no action specified.")
        except AttributeError:
            raise CommandError("unrecognized action: {}".format(action))
        return handler(options)

    def _do_create(self, profile_data):
        """
        Creates a new profile in the PayPal account with the specified id, using the specified data.
        """
        profile = WebProfile(profile_data)
        result = profile.create()
        if not result:
            raise CommandError("Could not create web profile: {}".format(profile.error))
        log.info("Created profile `%s` (id=%s).", profile.name, profile.id)
        return profile

    def _do_update(self, profile_id, profile_data):
        """
        Updates the existing profile in the PayPal account with the specified id, replacing
        all data with the specified data.
        """
        profile = WebProfile.find(profile_id)
        result = profile.update(profile_data)
        if not result:
            raise CommandError("Could not update web profile: {}".format(profile.error))
        # have to re-fetch to show the new state
        profile = WebProfile.find(profile_id)
        log.info("Updated profile %s.", profile.id)
        return profile

    def _do_enable(self, profile_id, profile_name):
        """
        Create a record in the PaypalWebProfile model that will be found and used to customize
        the payment page experience with PayPal checkouts.
        """
        try:
            __, created = PaypalWebProfile.objects.get_or_create(id=profile_id, name=profile_name)
            if created:
                log.info("Enabled profile `%s` (id=%s)", profile_name, profile_id)
            else:
                log.info("Profile `%s` (id=%s) is already enabled", profile_name, profile_id)
        except IntegrityError:
            # this should never happen, unless the data in the database has gotten out of
            # sync with the profiles stored in the PayPal account that this application
            # instance has been configured to use.
            raise CommandError(
                "Could not enable web profile because a profile with the same name exists under "
                "a different id.  This may indicate a configuration error, or simply stale data."
            )

    def handle_list(self, args):  # pylint: disable=unused-argument
        """Wrapper for paypalrestsdk List operation."""
        profiles = WebProfile.all()
        result = []
        try:
            result = [profile.to_dict() for profile in profiles]
        except KeyError:
            # weird internal paypal sdk behavior; it means the result was empty.
            pass
        self.print_json(result)

    def handle_create(self, options):
        """Wrapper for paypalrestsdk Create operation."""
        if not options.get('json'):
            raise CommandError("Action `create` requires a JSON string to be specified.")
        profile_data = json.loads(options.get('json'))
        profile = self._do_create(profile_data)
        self.print_json(profile.to_dict())

    def handle_show(self, options):
        """Wrapper for paypalrestsdk Find operation."""
        if not options.get('profile_id'):
            raise CommandError("Action `show` requires a profile_id to be specified.")
        profile_id = options.get('profile_id')
        profile = WebProfile.find(profile_id)
        self.print_json(profile.to_dict())

    def handle_update(self, options):
        """Wrapper for paypalrestsdk Update operation.  This completely replaces the value of the existing profile."""
        if not options.get('profile_id'):
            raise CommandError("Action `update` requires a profile_id to be specified.")
        if not options.get('json'):
            raise CommandError("Action `update` requires a JSON string to be specified.")
        profile_id = options.get('profile_id')
        profile_data = json.loads(options.get('json'))
        profile = self._do_update(profile_id, profile_data)
        self.print_json(profile.to_dict())

    def handle_delete(self, options):
        """
        Delete a web profile from the configured PayPal account.

        Before deleting this function checks to make sure a matching profile is not
        presently enabled.  If the specified profile is enabled the command will fail
        with an error, since leaving things in that state would cause the application
        to send invalid profile ids to PayPal, causing errors.
        """
        if not options.get('profile_id'):
            raise CommandError("Action `delete` requires a profile_id to be specified.")
        profile_id = options.get('profile_id')
        if PaypalWebProfile.objects.filter(id=profile_id).exists():
            raise CommandError(
                "Web profile {} is currently enabled.  You must disable it before you can delete it.".format(profile_id)
            )

        profile = WebProfile.find(profile_id)
        if not profile.delete():
            raise CommandError("Could not delete web profile: {}".format(profile.error))
        log.info("Deleted profile: %s", profile.id)
        self.print_json(profile.to_dict())

    def handle_enable(self, options):
        """
        Given the id of an existing web profile, save a reference to it in the database.

        When PayPal checkouts are set up, we can look this profile up by name and, if
        found, specify its id in our API calls to customize the payment page accordingly.
        """
        if not options.get('profile_id'):
            raise CommandError("Action `enable` requires a profile_id to be specified.")
        profile_id = options.get('profile_id')
        profile = WebProfile.find(profile_id)
        self._do_enable(profile.id, profile.name)

    def handle_disable(self, options):
        """
        Given the id of an existing web profile, find and delete any references to it
        in the database.  This reverses the effect of `handle_enable` above.
        """
        if not options.get('profile_id'):
            raise CommandError("Action `disable` requires a profile_id to be specified.")
        profile_id = options.get('profile_id')
        try:
            PaypalWebProfile.objects.get(id=profile_id).delete()
            log.info("Disabled profile %s.", profile_id)
        except PaypalWebProfile.DoesNotExist:
            log.info("Did not find an enabled web profile with id %s to disable.", profile_id)
