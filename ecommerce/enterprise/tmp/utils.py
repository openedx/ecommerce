import json
import os

from django.contrib.auth.models import User


def dummy_data(key):
    def wrapper(func):
        def wrapped(user, *args, **kwargs):
            if key == "learner" and getattr(user, "username", None) == "honor":
                return {}
            with open(os.path.dirname(__file__) + "/enterprise-learner.json") as json_file:
                return json.load(json_file).get(key, {})

        return wrapped
    return wrapper
