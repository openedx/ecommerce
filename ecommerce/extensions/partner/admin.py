

from django.utils.translation import ugettext_lazy as _
from oscar.apps.partner.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
from oscar.core.loading import get_class

Catalog = get_class('catalogue.models', 'Catalog')

admin.site.unregister((StockRecord, Partner,))


@admin.register(StockRecord)
class StockRecordAdminExtended(admin.ModelAdmin):
    list_display = ('product', 'partner', 'partner_sku', 'price_excl_tax', 'cost_price', 'num_in_stock')
    list_filter = ('partner',)
    raw_id_fields = ('product',)


@admin.register(Catalog)
class CatalogAdmin(admin.ModelAdmin):
    list_display = ('name', 'partner')
    search_fields = ('name', 'partner__name')
    list_filter = ('partner',)

    def render_change_form(self, request, context, *args, **kwargs):  # pylint: disable=arguments-differ
        if 'partner' in context['adminform'].form.fields:
            context['adminform'].form.fields['partner'].help_text = _(
                u"Click 'Save and Continue Editing' to add stock records"
            )
        return super(CatalogAdmin, self).render_change_form(request, context, *args, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj:
            readonly_fields.extend(['partner'])
        return readonly_fields

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        catalog_obj = self.get_object_updated(request, Catalog)
        if db_field.name == 'stock_records':
            if catalog_obj:
                kwargs['queryset'] = StockRecord.objects.filter(partner=catalog_obj.partner)
            else:
                # Assigning None to queryset raises the error.
                # To assign it an empty queryset just filter with id=None
                kwargs['queryset'] = StockRecord.objects.none()

        return super(CatalogAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_object_updated(self, request, model):
        object_id = request.META['PATH_INFO'].strip('/').split('/')[-2]
        if object_id and object_id.isdigit():
            return model.objects.get(pk=object_id)
        return None


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    # NOTE: Do not include the users field. The users table will grow so large
    # as to make the page timeout. Additionally, we don't actually make use of the field.
    fields = ('name', 'short_code', 'default_site',)
    list_display = ('name', 'default_site')
