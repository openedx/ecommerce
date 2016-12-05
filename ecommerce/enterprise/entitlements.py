
class EntitlementCondition(object):
    """
    Base class for condition that learner must satisfy in order to be eligible for
    entitlement.
    """
    def __init__(self, enterprise_customer):
        self.enterprise_customer = enterprise_customer

    def satisfies(self):
        pass


class DataSharingConsentCondition(EntitlementCondition):
    """
    Data sharing consent condition that will not be satisfied if enterprise customer
    requires data sharing consent and learner has not agreed to it.
    """
    USER_DATA_SHARING_STATES = ("agrees", "active", )
    EC_REQUIRES_DATA_SHARING = ("required", "enforced")

    def __init__(self, data_sharing_consent, enterprise_customer):
        super(DataSharingConsentCondition, self).__init__(enterprise_customer)
        self.data_sharing_consent = data_sharing_consent

    def is_satisfied(self):
        if self.enterprise_customer.data_sharing in self.EC_REQUIRES_DATA_SHARING:
            return self.data_sharing_consent in self.USER_DATA_SHARING_STATES
        return True


class Entitlements(object):
    def __init__(self, conditions):
        self.conditions = conditions

    def is_eligible(self):
        return all([condition.is_satisfied() for condition in self.conditions])
