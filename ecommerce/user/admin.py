from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from ecommerce.user.models import User


class EcommerceUserAdmin(UserAdmin):
    pass


admin.site.register(User, EcommerceUserAdmin)
