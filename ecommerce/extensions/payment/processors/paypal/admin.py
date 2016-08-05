from django.contrib import admin

from ecommerce.extensions.payment.processors.paypal.models import PaypalConfiguration, PaypalWebProfile


@admin.register(PaypalConfiguration)
class PaypalConfigurationAdmin(admin.ModelAdmin):
    list_display = ('active', 'site', 'client_id', 'mode')

    def get_form(self, request, obj=None, **kwargs):
        if obj and obj.pk:
            # Exclude encrypted fields from admin form for existing models
            self.exclude = ('client_secret',)
        else:
            self.exclude = ()
        return super(PaypalConfigurationAdmin, self).get_form(request, obj, **kwargs)


@admin.register(PaypalWebProfile)
class PaypalWebProfileAdmin(admin.ModelAdmin):
    pass
