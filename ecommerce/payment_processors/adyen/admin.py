from django.contrib import admin

from ecommerce.payment_processors.adyen.models import AdyenConfiguration


@admin.register(AdyenConfiguration)
class AdyenConfigurationAdmin(admin.ModelAdmin):
    pass
