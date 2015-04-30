from oscar.apps.catalogue.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import


class ProductAdminExtended(ProductAdmin):
    list_display = ('get_title', 'upc', 'get_product_class', 'structure',
                    'attribute_summary', 'date_created', 'course')


admin.site.unregister(Product)
admin.site.register(Product, ProductAdminExtended)
