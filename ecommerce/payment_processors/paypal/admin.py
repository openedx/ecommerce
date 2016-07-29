from django.contrib import admin

from ecommerce.payment_processors.paypal.models import PaypalConfiguration, PaypalWebProfile


@admin.register(PaypalConfiguration)
class PaypalConfigurationAdmin(admin.ModelAdmin):
    pass


@admin.register(PaypalWebProfile)
class PaypalWebProfileAdmin(admin.ModelAdmin):
    pass
