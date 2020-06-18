

from waffle.models import Switch


def toggle_switch(name, active):
    """
    Activate or deactivate a feature switch.

    The switch is created if it does not exist.

    Arguments:
        name (str): name of the switch to be toggled
        active (bool): boolean indicating if the switch should be activated or deactivated

    Returns:
        Switch: Waffle Switch
    """
    switch, __ = Switch.objects.get_or_create(name=name, defaults={'active': active})
    switch.active = active
    switch.save()
    switch.flush()
    return switch
