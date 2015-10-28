def get_partner_for_site(request):
    """ Returns the Partner associated with the request. """
    return request.site.siteconfiguration.partner
