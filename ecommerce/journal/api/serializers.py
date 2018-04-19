"""Journal API Serializers"""
from oscar.core.loading import get_model
from rest_framework import serializers

Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductAttributeValue = get_model('catalogue', 'ProductAttributeValue')
StockRecord = get_model('partner', 'StockRecord')


class AttributesSerializer(serializers.ModelSerializer):
    """ Serializer for ProductAttributeValue objects. """
    name = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()
    value = serializers.CharField(max_length=256)

    def get_name(self, instance):
        return instance.attribute.name

    def get_code(self, instance):
        return instance.attribute.code

    class Meta(object):
        model = ProductAttributeValue
        fields = ('name', 'code', 'value',)


class StockRecordSerializer(serializers.ModelSerializer):
    """ Serializer for stock record objects. """
    partner = serializers.SlugRelatedField(slug_field='short_code', queryset=Partner.objects.all())

    class Meta(object):
        model = StockRecord
        fields = ('partner', 'partner_sku', 'price_currency', 'price_excl_tax',)


class StockRecordSerializerForUpdate(StockRecordSerializer):
    """
    Stock record objects serializer for PUT requests.
    Allowed fields to update are 'price_currency' and 'price_excl_tax'.
    """

    class Meta(object):
        model = StockRecord
        fields = ('price_currency', 'price_excl_tax',)


class JournalProductSerializer(serializers.ModelSerializer):
    """
    Serializer for the Journal Product model.
    """
    product_class = serializers.SlugRelatedField(slug_field='name', queryset=ProductClass.objects.all())
    attribute_values = AttributesSerializer(many=True)
    stockrecords = StockRecordSerializer(many=True)

    def create(self, validated_data):
        attributes_data = validated_data.pop('attribute_values')
        stockrecord_data = validated_data.pop('stockrecords')
        product = Product.objects.create(**validated_data)

        # Create the AttributeValues
        product_class = ProductClass.objects.get(id=product.product_class_id)
        # TODO - get attribute name and code from serializer and use in lookup of ProductAttribute
        product_attribute = ProductAttribute.objects.get(product_class__id=product_class.id)

        for attribute in attributes_data:
            ProductAttributeValue.objects.create(
                product=product, attribute=product_attribute, value_text=attribute['value']
            )

        for stockrecord in stockrecord_data:
            StockRecord.objects.create(
                product=product,
                partner=stockrecord['partner'],
                partner_sku=stockrecord['partner_sku'],
                price_currency=stockrecord['price_currency'],
                price_excl_tax=stockrecord['price_excl_tax']
            )

        return product

    class Meta(object):
        model = Product
        fields = ('id', 'structure', 'attribute_values', 'product_class', 'title', 'expires', 'stockrecords')


class JournalProductUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer to update the Journal Product model.
    """
    stockrecords = StockRecordSerializerForUpdate(many=True, required=False)

    def update(self, instance, validated_data):
        title = validated_data.pop('title', None)
        stockrecord_data = validated_data.pop('stockrecords', None)

        # update stockrecords, if any
        if stockrecord_data:
            stockrecords = instance.stockrecords.all()
            for index, stockrecord in enumerate(stockrecords):
                stockrecord.price_currency = stockrecord_data[index]['price_currency']
                stockrecord.price_excl_tax = stockrecord_data[index]['price_excl_tax']
                stockrecord.save()

        # update title
        if title:
            instance.title = title
            instance.save()

        return instance

    class Meta(object):
        model = Product
        fields = ('title', 'stockrecords')
