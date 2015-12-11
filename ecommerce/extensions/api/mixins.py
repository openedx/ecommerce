from oscar.core.loading import get_class
from rest_framework import serializers

Selector = get_class('partner.strategy', 'Selector')


class ProductInfoMixin(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    def get_info(self, request, product):
        """Return the appropriate ``PurchaseInfo`` instance."""
        return Selector().strategy(request=request).fetch_for_product(product)

    def get_price(self, product):
        request = self.context.get('request')
        info = self.get_info(request, product)
        if info.availability.is_available_to_buy:
            return serializers.DecimalField(max_digits=10, decimal_places=2).to_representation(info.price.excl_tax)
        return None
