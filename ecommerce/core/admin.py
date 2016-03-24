from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from ecommerce.core.models import BusinessClient, SiteConfiguration, User


class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ('site', 'partner', 'lms_url_root', 'theme_scss_path', 'payment_processors')
    search_fields = ['site__name']


class EcommerceUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'full_name', 'first_name', 'last_name', 'is_staff')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(BusinessClient)
class BusinessClientAdmin(admin.ModelAdmin):
    pass

admin.site.register(SiteConfiguration, SiteConfigurationAdmin)
admin.site.register(User, EcommerceUserAdmin)
