from .resource import List, Find, Create, Delete, Update, Replace


class WebProfile(Create, Find, List, Delete, Update, Replace):
    """The payment experience api allows merchants to provide a
    customized experience to consumers from the merchant's website
    to the PayPal payment. API docs at
    https://developer.paypal.com/docs/api/#payment-experience

    Usage::

        >>> web_profile = WebProfile.find("XP-3NWU-L5YK-X5EC-6KJM")
    """
    path = "/v1/payment-experience/web-profiles"

WebProfile.convert_resources['web_profile'] = WebProfile
