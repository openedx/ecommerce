from django.contrib import admin

from ecommerce.extensions.payment.processors.cybersource.models import CybersourceConfiguration


@admin.register(CybersourceConfiguration)
class CybersourceConfigurationAdmin(admin.ModelAdmin):
    list_display = ('active', 'site', 'merchant_id', 'profile_id')
