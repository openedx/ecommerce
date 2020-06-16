

from ecommerce.extensions.fulfillment.modules import BaseFulfillmentModule
from ecommerce.extensions.fulfillment.status import LINE


class MockFulfillmentModule(BaseFulfillmentModule):
    def supports_line(self, line):
        """ Supported lines for refund. """

    def get_supported_lines(self, lines):
        """Returns a list of lines this mock module supposedly supports."""

    def fulfill_product(self, order, lines, email_opt_in=False):
        """Fulfill product. Mark all lines success."""

    def revoke_line(self, line):
        """ Always revoke the product. """


class FakeFulfillmentModule(MockFulfillmentModule):
    """Fake Fulfillment Module used to test the API without specific implementations."""

    def supports_line(self, line):
        return True

    def get_supported_lines(self, lines):
        """Returns a list of lines this Fake module supposedly supports."""
        return lines

    def fulfill_product(self, order, lines, email_opt_in=False):
        """Fulfill product. Mark all lines success."""
        for line in lines:
            line.set_status(LINE.COMPLETE)

    def revoke_line(self, line):
        """ Always revoke the product. """
        return True


class FulfillmentNothingModule(MockFulfillmentModule):
    """Fake Fulfillment Module that refuses to fulfill anything."""

    def supports_line(self, line):
        return False

    def get_supported_lines(self, lines):
        """Returns an empty list, because this module supports nothing."""
        return []


class RevocationFailureModule(MockFulfillmentModule):
    """ This module supports all Lines, but fulfills none. Use it to test revocation failures. """

    def get_supported_lines(self, lines):
        """ Returns the lines passed to indicate the module supports fulfilling all of them."""
        return lines

    def supports_line(self, line):
        """ Returns True since the module supports fulfillment of all Lines."""
        return True

    def revoke_line(self, line):
        """ Returns False to simulate a revocation failure."""
        return False
