def get_partner_for_site(request):
    """ Returns the Partner associated with the request. """
    if not request:
        return None

    return request.site.siteconfiguration.partner
