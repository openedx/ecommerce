"""
Helper methods for enterprise app.
"""
from django.conf import settings
import waffle


def is_enterprise_feature_enabled():
    """
    Returns boolean indicating whether enterprise feature is enabled or
    disabled.

    Example:
        >> is_enterprise_feature_enabled()
        True

    Returns:
         (bool): True if enterprise feature is enabled else False

    """
    is_enterprise_enabled = waffle.switch_is_active(settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH)
    return is_enterprise_enabled
