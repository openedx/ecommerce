import waffle
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from ecommerce.core.constants import USER_LIST_VIEW_SWITCH
from ecommerce.core.models import BusinessClient, SiteConfiguration, User


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ('site', 'partner', 'lms_url_root', 'payment_processors')
    search_fields = ['site__name']


@admin.register(User)
class EcommerceUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'full_name', 'first_name', 'last_name', 'is_staff')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    show_full_result_count = False

    def changelist_view(self, request, extra_context=None):
        if not waffle.switch_is_active(USER_LIST_VIEW_SWITCH):
            self.change_list_template = 'admin/disable_change_list.html'
        else:
            self.change_list_template = None

        return super(EcommerceUserAdmin, self).changelist_view(request, extra_context)


@admin.register(BusinessClient)
class BusinessClientAdmin(admin.ModelAdmin):
    pass
