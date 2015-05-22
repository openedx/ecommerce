from django.dispatch import Signal

# This signal should be emitted after a refund is completed--payment credited AND fulfillment revoked.
post_refund = Signal(providing_args=["refund"])

# TODO Track refund: https://support.google.com/analytics/answer/1037443?hl=en
