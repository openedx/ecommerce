# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django import forms
from django.contrib.auth.forms import UserChangeForm
from edx_rbac.admin.forms import UserRoleAssignmentAdminForm

from ecommerce.core.models import EcommerceFeatureRoleAssignment


class EcommerceFeatureRoleAssignmentAdminForm(UserRoleAssignmentAdminForm):
    """
    Admin form for EcommerceFeatureRoleAssignmentAdmin
    """

    class Meta:
        """
        Meta class for EcommerceFeatureRoleAssignmentAdminForm.
        """

        model = EcommerceFeatureRoleAssignment
        fields = '__all__'


class EcommerceUserChangeForm(UserChangeForm):
    """
    Admin form for EcommerceUserChange
    """
    # This is the recommended solution by Django to preserve the 30 character limit.
    # This is necessary in preparation for the Django 2 upgrade, because the upcoming
    # migration to increase the length of last_name is being faked for edx.org in
    # Production to avoid this large migration.
    # See https://docs.djangoproject.com/en/3.0/releases/2.0/#abstractuser-last-name-max-length-increased-to-150
    last_name = forms.CharField(max_length=30, required=False)
