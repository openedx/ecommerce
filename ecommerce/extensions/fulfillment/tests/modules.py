from ecommerce.extensions.fulfillment.modules import BaseFulfillmentModule
from ecommerce.extensions.fulfillment.status import LINE


class MockFulFillmentModule(BaseFulfillmentModule):
    def get_supported_lines(self, order, lines):
        pass

    def fulfill_product(self, order, lines):
        pass

    def revoke_product(self, order, lines):
        pass


class FakeFulfillmentModule(MockFulFillmentModule):
    """Fake Fulfillment Module used to test the API without specific implementations."""

    def get_supported_lines(self, order, lines):
        """Returns a list of lines this Fake module supposedly supports."""
        return lines

    def fulfill_product(self, order, lines):
        """Fulfill product. Mark all lines success."""
        for line in lines:
            line.set_status(LINE.COMPLETE)


class FulfillmentNothingModule(MockFulFillmentModule):
    """Fake Fulfillment Module that refuses to fulfill anything."""

    def get_supported_lines(self, order, lines):
        """Returns an empty list, because this module supports nothing."""
        return []
