"""Helper functions for working with payment processor classes."""
import hmac
import base64
import hashlib

from django.utils import importlib


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
    processor_class = getattr(importlib.import_module(module_path), class_name)

    return processor_class


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
