"""
Experimentation utilities
"""

import hashlib
import logging
import re

logger = logging.getLogger(__name__)


def stable_bucketing_hash_group(group_name, group_count, username):
    """
    An implementation of a stable bucketing algorithm that can be used
    to reliably group users into experiments.

    Return the bucket that a user should be in for a given stable bucketing assignment.

    This is duplicated from edx-platform as we frequently base experiments on this
    mechanism but don't want to create a formal dependency nor create a separate package
    for one small function. Original is here:
        https://github.com/edx/edx-platform/blob/master/lms/djangoapps/experiments/stable_bucketing.py

    Arguments:
        group_name: The name of the grouping/experiment.
        group_count: How many groups to bucket users into.
        username: The username of the user being bucketed.
    """
    hasher = hashlib.md5()
    hasher.update(group_name.encode('utf-8'))
    hasher.update(username.encode('utf-8'))
    hash_str = hasher.hexdigest()

    return int(re.sub('[8-9a-f]', '1', re.sub('[0-7]', '0', hash_str)), 2) % group_count
