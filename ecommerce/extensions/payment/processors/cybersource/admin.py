from django.contrib import admin

from ecommerce.extensions.payment.processors.cybersource.models import CybersourceConfiguration


@admin.register(CybersourceConfiguration)
class CybersourceConfigurationAdmin(admin.ModelAdmin):
    list_display = ('active', 'site', 'merchant_id', 'profile_id')

    def get_form(self, request, obj=None, **kwargs):
        if obj and obj.pk:
            # Exclude encrypted fields from admin form for existing models
            self.exclude = ('secret_key', 'transaction_key')
        else:
            self.exclude = ()
        return super(CybersourceConfigurationAdmin, self).get_form(request, obj, **kwargs)
