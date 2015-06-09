from oscar.apps.catalogue.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import
from simple_history.admin import SimpleHistoryAdmin


class ProductAdminExtended(SimpleHistoryAdmin):
    list_display = ('get_title', 'upc', 'get_product_class', 'structure', 'attribute_summary', 'date_created', 'course')
    prepopulated_fields = {"slug": ("title",)}
    inlines = [AttributeInline, CategoryInline, ProductRecommendationInline]


admin.site.unregister(Product)
admin.site.register(Product, ProductAdminExtended)


class ProductAttributeValueAdminExtended(SimpleHistoryAdmin):
    list_display = ('product', 'attribute', 'value')


admin.site.unregister(ProductAttributeValue)
admin.site.register(ProductAttributeValue, ProductAttributeValueAdminExtended)
