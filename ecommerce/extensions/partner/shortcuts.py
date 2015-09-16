from django.contrib.sites.shortcuts import get_current_site
from django.contrib.sites.models import Site


def get_partner_for_site(request):
    """Get the partner for the requested site"""
    try:
        site = get_current_site(request)
    except Site.DoesNotExist:
        return None

    return site.siteconfiguration.partner
