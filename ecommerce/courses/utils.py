def mode_for_seat(seat):
    """ Returns the Enrollment mode for a given seat product. """
    certificate_type = getattr(seat.attr, 'certificate_type', '')

    if certificate_type == 'professional' and not seat.attr.id_verification_required:
        return 'no-id-professional'
    elif certificate_type == '':
        return 'audit'

    return certificate_type
