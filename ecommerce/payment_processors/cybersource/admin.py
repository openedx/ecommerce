from django.contrib import admin

from ecommerce.payment_processors.cybersource.models import CybersourceConfiguration


@admin.register(CybersourceConfiguration)
class CybersourceConfigurationAdmin(admin.ModelAdmin):
    pass
