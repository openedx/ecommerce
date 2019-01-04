3. Enterprise Coupons
---------------------

Status
------

Accepted

Context
-------

Coupons have increasingly become an integral delivery method for Enterprise Customers who do not have integrations with
our system, however the experience of administering the codes is comparatively rudimentary. As part of the team’s
efforts to provide valuable administrative tooling to Enterprise Customers, we decided to build a Code Management
screen in the Enterprise Admin Portal.

In order to support the Code Management screen, which is an independently deployed microfrontend built in React backed
by api calls, we would need to change the Ecommerce service, which contains Coupons. The screen had three high level
requirements:

* The ability to list details about an Enterprise Customer's Coupons and the codes contained therein.
* The ability to assign a code usage to a user, and the ability to revoke the code or remind the user once assigned.
* Support existing Coupons in the system used by Enterprise Customers with this new functionality.

In addition to figuring out how to build api endpoints to do this, we had to confront the existing Coupon system which
was poorly understood in how it was used and how it worked. This meant that we would need to refactor some of this code
to support the new features after having a better understanding of the current state.

Finally, since the introduction of Enterprise Customer Catalogs the Customer Success team has moved towards using them
across different parts of the system. The first introduction of Enterprise Customer Catalogs came with Enterprise Offer,
which are site-wide Conditional Offers that are applied to user’s baskets when they are linked to an
Integrated Enterprise Customer. When Enterprise Customer Catalog support was added for Coupons, we inadvertently ended
up with two different ways Conditional Offers could be evaluated with Enterprise data, introducing unnecessary
complexity to an already confusing part of the system.

Decision
--------

We made three decisions to support the Code Management Screen: clearly define Enterprise Coupons separately from other
Coupons, extend the Enterprise Conditional Offer to support the broader set of assignment functionality, and add a new
usage type for a code to be used many times by only one user.

**Defining Enterprise Coupons**

The decision to separate Enterprise Coupons was influenced by two problems. The first was the existing complexity of
different Coupon configuration options, which would balloon the scope and complexity of adding the ability to assign
codes. In particular, there were 5 ways to specify which courses are valid for a coupon: picking an individual course,
giving a discovery service query to evaluate, picking a Catalog object from the discovery service, picking a Program,
and picking and Enterprise Customer Catalog. The different redemption types, SINGLE_USE, MULTI_USE, and
ONCE_PER_CUSTOMER also brought on additional complexity, but we had to keep these options because of business use cases
for each. The second problem was the fact that we had two different configurations of data for Conditional Offers that
could get evaluated for Enterprise Customers and Catalogs, and we wanted to consolidate this data to be specified and
evaluated in one way.

As a result, we did the following:

1. Modified the existing Coupon screen to create Enterprise Conditional Offers for each Voucher for each Coupon with
   Enterprise data.

   * This is in addition to the previously existing Conditional Offer.

2. Introduced a waffle switch to control which Conditional Offer to use for codes with Enterprise data (and thus two
   Conditional Offers).

   * This waffle switch will be deprecated after it is turned on and the feature is stable.

3. Added enterprise_customer_uuid to the BusinessClient model, in order to tie top level Coupon objects (which are
   Products under the hood) to an Enterprise Customer when the field is set for a Coupon.

   * Previously, Enterprise Customer was stored only on the Range object, which is difficult to trace back to a
     specific Coupon.

4. Introduced a new edX Operator admin screen for administering Enterprise Coupons.

   * This screen displays only Coupons with Enterprise data that have Enterprise Conditional Offers created for their
     underlying codes.
   * This screen eliminates all the other course specification options except for Enterprise Customer Catalog, and
     enforces that Enterprise Customer and Enterprise Customer Catalog are set for the Coupon.

Thus, Enterprise Coupons are now defined and created separately from other Coupons as Coupons with a BusinessClient
object that has an enterprise_customer_uuid, and codes which have Enterprise Conditional Offers with an Enterprise
Customer and Enterprise Customer Catalog.

**Extending Enterprise Conditional Offers**

After reading through the Django Oscar documentation, it was clear there was no native support for enforcing that a
code be redeemed by a particular user. This meant we would have to extend Oscar further to support this capability. The
most logical place to extend is the Conditional Offer, since according to the Django Oscar documentation, it is the
class and data model that handle defining what conditions must be true for a benefit to be applied to a basket.

The Enterprise Conditional Offer class already enforces the conditions relevant to an Enterprise Customer, mainly that
the user is linked to the configured Enterprise Customer, and that the course is part of the Enterprise Customer Catalog.
Because we intend to have the assignment functionality for the Enterprise Customer, it makes sense to extend the
Enterprise Conditional Offer to achieve this.

We created a new model called OfferAssignment to track the lifecycle of an assignment, with the following fields: offer
(foreign key to ConditionalOffer), code, user_email, status, voucher_application (foreign key to VoucherApplication).
We also created an api endpoint to create assignments and another endpoint to revoke existing assignments.

When a code is assigned to a user through the api, if there are enough possible redemptions left on the codes specified,
a new OfferAssignment is created for each user email, with an initial status of  OFFER_ASSIGNMENT_EMAIL_PENDING. This
status gets updated to OFFER_ASSIGNED once an email to the user is successfully delivered. An OfferAssignment in this
state works as something like a reservation for the code - depending on the code type and the usage limit for the code,
the existence of an OfferAssignment guarantees that user one redemption, but does not preclude other users redeeming the
code if they do not have an OfferAssignment and there are available redemptions. This is enforced upon redemption by
logic in the AssignableEnterpriseCustomerCondition class.

When a code is revoked from a user, given that the user has an OfferAssignment for that code that had not been redeemed
yet, the OfferAssignment is updated with the status of OFFER_ASSIGNMENT_REVOKED. This effectively rescinds the user’s
reservation on that code; they may still be able to redeem the code if redemptions are available, but they are not
guaranteed a spot. This is also enforced by the AssignableEnterpriseCustomerCondition class.

Once the a code is redeemed by a user for which an OfferAssignment exists, the record is updated to have a status of
OFFER_REDEEMED and the voucher_application field is updated to the resulting VoucherApplication row that was created.

**New Usage Type**

The final requirement set for product was the introduction of a new usage type, MULTI_USE_PER_CUSTOMER, which meant
that a single Voucher could be used multiple times, but by only one user. This feature would depend on OfferAssignment
to enforce that the same user was entitled to redemptions for a single code.

To achieve this, we extended the Voucher model to include this new usage type constant, and updated the Enterprise
Coupon admin screen only to include the new usage type as an option. This means only Enterprise Coupons can have this
usage type.

Next, we included logic in the assignment api endpoint to create an OfferAssignment for each usage of the code for that
user, so that all available slots would be assigned to the user. In the revoke api, all OfferAssignment rows for that
user and code are updated with the status of OFFER_ASSIGNMENT_REVOKED. Once these codes are revoked, unlike other usage
types, the code is effectively unusable by both the original assigned user or any other user. This is enforced by the
AssignableEnterpriseCustomerCondition class.

If a code of this type is redeemed before it is assigned, during order fulfillment, OfferAssignment rows for that user
and code are written for the remaining usages of that code.

Consequences
------------

As a result of these changes, here is a summary of what will be different, going forward:

* Coupons with enterprise data will be maintained through a separate admin screen, with different configuration options
  than other Coupons. They will be referred to specifically as Enterprise Coupons. The underlying creation/update logic
  is largely the same, with Enterprise Coupon logic selectively overriding where needs differ. Enterprise Coupons must
  have an Enterprise Customer and Enterprise Customer Catalog configured.
* The underlying ConditionalOffer model/class for both Enterprise Coupons and Enterprise Offers will now be shared.
* Enterprise Coupons will have the ability for codes within to be assigned to specific users, with the option to revoke
  codes. Assignments act like reservations to use the code for SIGNLE_USE, ONCE_PER_CUSTOMER, and MULTI_USE coupons.
* Enterprise Coupons will have a new usage type option, MULTI_USE_PER_CUSTOMER, where each code has multiple usages
  that must be used by a single user. When these codes are revoked, they are no longer usable.

References
----------
