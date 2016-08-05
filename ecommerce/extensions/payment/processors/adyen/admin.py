from django.contrib import admin

from ecommerce.extensions.payment.processors.adyen.models import AdyenConfiguration


@admin.register(AdyenConfiguration)
class AdyenConfigurationAdmin(admin.ModelAdmin):
    list_display = ('active', 'site', 'merchant_account_code', 'web_service_username')

    def get_form(self, request, obj=None, **kwargs):
        if obj and obj.pk:
            # Exclude encrypted fields from admin form for existing models
            self.exclude = ('notifications_hmac_key', 'web_service_password')
        else:
            self.exclude = ()
        return super(AdyenConfigurationAdmin, self).get_form(request, obj, **kwargs)
