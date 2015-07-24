def mode_for_seat(seat):
    """ Returns the Enrollment mode for a given seat product. """
    certificate_type = seat.attr.certificate_type

    if certificate_type == 'professional' and not seat.attr.id_verification_required:
        return 'no-id-professional'

    return certificate_type
