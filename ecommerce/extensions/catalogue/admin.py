from oscar.apps.catalogue.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import
from simple_history.admin import SimpleHistoryAdmin

admin.site.unregister((Product, ProductAttributeValue,))


@admin.register(Product)
class ProductAdminExtended(SimpleHistoryAdmin):
    list_display = ('get_title', 'upc', 'get_product_class', 'structure', 'attribute_summary', 'date_created', 'course',
                    'expires',)
    prepopulated_fields = {"slug": ("title",)}
    inlines = [AttributeInline, CategoryInline, ProductRecommendationInline]
    show_full_result_count = False
    raw_id_fields = ('course',)


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdminExtended(SimpleHistoryAdmin):
    list_display = ('product', 'attribute', 'value')
    show_full_result_count = False
