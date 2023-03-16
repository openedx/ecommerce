from django.contrib import admin
from solo.admin import SingletonModelAdmin

from ecommerce.extensions.iap.models import IAPProcessorConfiguration, PaymentProcessorResponseExtension

admin.site.register(IAPProcessorConfiguration, SingletonModelAdmin)


@admin.register(PaymentProcessorResponseExtension)
class PaymentProcessorResponseExtensionAdmin(admin.ModelAdmin):
    list_display = ('original_transaction_id', 'processor_response')
