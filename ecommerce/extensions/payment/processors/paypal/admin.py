from django.contrib import admin

from ecommerce.extensions.payment.processors.paypal.models import PaypalConfiguration, PaypalWebProfile


@admin.register(PaypalConfiguration)
class PaypalConfigurationAdmin(admin.ModelAdmin):
    list_display = ('active', 'site', 'client_id', 'mode')


@admin.register(PaypalWebProfile)
class PaypalWebProfileAdmin(admin.ModelAdmin):
    pass
