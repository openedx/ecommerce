"""
Exception classes for enterprise app.
"""


class RequiresDataSharingError(Exception):
    """
    Exception is raised when a learner needs to consent for data sharing before getting the entitlements
    """
