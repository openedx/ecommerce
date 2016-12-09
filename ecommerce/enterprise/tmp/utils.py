import json
import os


def dummy_data(key):
    def wrapper(func):
        def wrapped(*args, **kwargs):
            with open(os.path.dirname(__file__) + "/enterprise-learner.json") as json_file:
                return json.load(json_file).get(key, {})

        return wrapped
    return wrapper
