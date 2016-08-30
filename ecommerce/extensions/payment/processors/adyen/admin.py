from django.contrib import admin

from ecommerce.extensions.payment.processors.adyen.models import AdyenConfiguration


@admin.register(AdyenConfiguration)
class AdyenConfigurationAdmin(admin.ModelAdmin):
    list_display = ('active', 'site', 'merchant_account_code', 'web_service_username')
