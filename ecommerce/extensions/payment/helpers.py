"""Helper functions for working with payment processor classes."""


import base64
import hashlib
import hmac
from importlib import import_module

from django.conf import settings

from ecommerce.extensions.payment import exceptions


def get_processor_class(path):
    """Return the payment processor class at the specified path.

    Arguments:
        path (string): Fully-qualified path to a payment processor class.

    Returns:
        class: The payment processor class at the specified path.

    Raises:
        ImportError: If no module with the parsed module path exists.
        AttributeError: If the module located at the parsed module path
            does not contain a class with the parsed class name.
    """
    module_path, _, class_name = path.rpartition('.')
    processor_class = getattr(import_module(module_path), class_name)

    return processor_class


def get_default_processor_class():
    """Return the default payment processor class.

    Returns:
        class: The payment processor class located at the first path
            specified in the PAYMENT_PROCESSORS setting.

    Raises:
        IndexError: If the PAYMENT_PROCESSORS setting is empty.
    """
    processor_class = get_processor_class(settings.PAYMENT_PROCESSORS[0])

    return processor_class


def get_processor_class_by_name(name):
    """Return the payment processor class corresponding to the specified name.

    Arguments:
        name (string): The name of a payment processor.

    Returns:
        class: The payment processor class with the given name.

    Raises:
        ProcessorNotFoundError: If no payment processor with the given name exists.
    """
    for path in settings.PAYMENT_PROCESSORS:
        processor_class = get_processor_class(path)

        if name == processor_class.NAME:
            return processor_class

    raise exceptions.ProcessorNotFoundError(
        exceptions.PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE.format(name=name)
    )


def sign(message, secret):
    """Compute a Base64-encoded HMAC-SHA256.

    Arguments:
        message (unicode): The value to be signed.
        secret (unicode): The secret key to use when signing the message.

    Returns:
        unicode: The message signature.
    """
    message = message.encode('utf-8')
    secret = secret.encode('utf-8')

    # Calculate a message hash (i.e., digest) using the provided secret key
    digest = hmac.new(secret, msg=message, digestmod=hashlib.sha256).digest()

    # Base64-encode the message hash
    signature = base64.b64encode(digest).decode()

    return signature
