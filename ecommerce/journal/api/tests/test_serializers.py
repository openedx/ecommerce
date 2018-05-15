"""
Test cases to cover JournalProductSerializer.
"""
from oscar.core.loading import get_model
from oscar.test.factories import (
    ProductAttributeFactory,
    ProductAttributeValueFactory,
    ProductClassFactory,
    ProductFactory
)

from ecommerce.journal.api.serializers import (
    AttributesSerializer,
    JournalProductSerializer,
    JournalProductUpdateSerializer,
    StockRecordSerializer,
    StockRecordSerializerForUpdate
)
from ecommerce.tests.factories import PartnerFactory, StockRecordFactory
from ecommerce.tests.testcases import TestCase

StockRecord = get_model('partner', 'StockRecord')


class AttributesSerializerTest(TestCase):

    def setUp(self):
        super(AttributesSerializerTest, self).setUp()
        self.product_attribute = ProductAttributeValueFactory(
            value=0.2
        )

    def _get_expected_data(self):
        """ Returns expected data for serializer """
        return {
            "value": str(self.product_attribute.value),
            "code": self.product_attribute.attribute.code,
            "name": self.product_attribute.attribute.name
        }

    def test_serializer_data(self):
        """ Test AttributesSerializer return data properly. """
        self.assertEqual(
            AttributesSerializer(self.product_attribute).data,
            self._get_expected_data()
        )


class StockRecordSerializerTest(TestCase):

    def setUp(self):
        super(StockRecordSerializerTest, self).setUp()
        self.stock_record = StockRecordFactory(
            partner=PartnerFactory(
                short_code="dummy-partner"
            ),
            product=ProductFactory(
                categories=""
            )
        )

    def _get_expected_data(self):
        """ Returns expected data for serializer """
        return {
            "partner_sku": self.stock_record.partner_sku,
            "partner": self.stock_record.partner.short_code,
            "price_currency": self.stock_record.price_currency,
            "price_excl_tax": str(self.stock_record.price_excl_tax)
        }

    def test_serializer_data(self):
        """ Test serializer return data properly. """
        self.assertEqual(
            StockRecordSerializer(self.stock_record).data,
            self._get_expected_data()
        )


class StockRecordSerializerForUpdateTest(TestCase):

    def setUp(self):
        super(StockRecordSerializerForUpdateTest, self).setUp()
        self.stock_record = StockRecordFactory(
            partner=PartnerFactory(
                short_code="dummy-partner"
            ),
            product=ProductFactory(
                categories=""
            )
        )

    def _get_expected_data(self):
        """ Returns expected data for serializer """
        return {
            "price_currency": self.stock_record.price_currency,
            "price_excl_tax": str(self.stock_record.price_excl_tax)
        }

    def test_serializer_data(self):
        """ Test serializer return data properly. """
        self.assertEqual(
            StockRecordSerializerForUpdate(self.stock_record).data,
            self._get_expected_data()
        )


class JournalProductSerializerTest(TestCase):

    def setUp(self):
        super(JournalProductSerializerTest, self).setUp()
        product_class = ProductClassFactory(
            name="Journal"
        )
        self.product = ProductFactory(
            product_class=product_class,
            stockrecords=[],
            categories=""
        )
        StockRecordFactory(
            partner_sku="unit02",
            product=self.product,
            partner=PartnerFactory(
                short_code="dummy-partner"
            )
        )
        ProductAttributeValueFactory(
            value=0.2,
            product=self.product,
            attribute=ProductAttributeFactory(
                product_class=product_class
            )
        )

    def _get_expected_data(self):
        """ Returns expected data for serializer """
        return {
            "id": self.product.id,
            "title": self.product.title,
            "expires": self.product.expires,
            'structure': self.product.structure,
            "product_class": self.product.product_class.name,
            "stockrecords": StockRecordSerializer(self.product.stockrecords.all(), many=True).data,
            "attribute_values": AttributesSerializer(self.product.attribute_values.all(), many=True).data
        }

    def test_serializer_data(self):
        """ Test serializer return data properly. """
        self.assertEqual(
            JournalProductSerializer(self.product).data,
            self._get_expected_data()
        )


class JournalProductUpdateSerializerTest(TestCase):

    def setUp(self):
        super(JournalProductUpdateSerializerTest, self).setUp()
        product_class = ProductClassFactory(
            name="Journal"
        )
        self.product = ProductFactory(
            product_class=product_class,
            stockrecords=[],
            categories=""
        )
        StockRecordFactory(
            partner_sku="unit02",
            product=self.product,
            partner=PartnerFactory(
                short_code="dummy-partner"
            )
        )

    def _get_expected_data(self):
        """ Returns expected data for serializer """
        return {
            "title": self.product.title,
            "stockrecords": StockRecordSerializerForUpdate(self.product.stockrecords.all(), many=True).data
        }

    def test_serializer_data(self):
        """ Test serializer return data properly. """
        self.assertEqual(
            JournalProductUpdateSerializer(self.product).data,
            self._get_expected_data()
        )
