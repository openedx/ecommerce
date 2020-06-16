

import waffle
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _
from edx_rbac.admin import UserRoleAssignmentAdmin

from ecommerce.core.constants import USER_LIST_VIEW_SWITCH
from ecommerce.core.forms import EcommerceFeatureRoleAssignmentAdminForm
from ecommerce.core.models import BusinessClient, EcommerceFeatureRoleAssignment, SiteConfiguration, User


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

    def get_queryset(self, request):
        if not waffle.switch_is_active(USER_LIST_VIEW_SWITCH):
            # Translators: "Waffle" is the name of a third-party library. It should not be translated
            msg = _('User administration has been disabled due to the load on the database. '
                    'This functionality can be restored by activating the {switch_name} Waffle switch. '
                    'Be careful when re-activating this switch!').format(switch_name=USER_LIST_VIEW_SWITCH)

            self.message_user(request, msg, level=messages.WARNING)
            return User.objects.none()

        return super(EcommerceUserAdmin, self).get_queryset(request)


@admin.register(BusinessClient)
class BusinessClientAdmin(admin.ModelAdmin):
    """ Bussiness Client Admin. """


@admin.register(EcommerceFeatureRoleAssignment)
class EcommerceFeatureRoleAssignmentAdmin(UserRoleAssignmentAdmin):
    """
    Admin site for EcommerceFeatureRoleAssignment model
    """
    class Meta:
        """
        Meta class for EcommerceFeatureRoleAssignment admin model
        """
        model = EcommerceFeatureRoleAssignment
    form = EcommerceFeatureRoleAssignmentAdminForm
    fields = ('user', 'role', 'enterprise_id')
