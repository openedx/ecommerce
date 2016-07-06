Coupon Codes
============

A feature that adds the ability to create "Coupon Codes".  Coupon Codes are a product that is treated just like
any other product in Otto.


---------------------
Coupon Code Creation
---------------------
Coupons can be created using the Coupon Administration tool:
the URL path to this tool is
http://localhost:8002/coupons/

The Coupon Administration Tool allows the creation of two flavors of codes:

1. Discount Code

  Create one or many codes that offer a discount up to 99% of the cost of a given course.

2. Enrollment Code

  Create one or many codes that offer a 100% discount on the cost of a given course

Both types of Coupons can have the following behavior:

  - One time by one user

  - Multiple times by multiple users

  - One time by multiple users

The creation of a Coupon behind the scenes generates an order.  Payment for these orders is handled by the new
Invoice Payment Processor module and assumes out of band payment for the codes.

The Invoice Payment Modules records the transaction in the Invoice table for later reconciliation.


----------------------
Coupon Code Redemption
----------------------
There are two endpoints for redemption.

- Offer landing page:

http://localhost:8002/coupons/offer/?code=

This page displays the offer to the learner and allows the leaner to apply the code supplied.
This landing page does not require registration / login and is there to provide
context as well as to confirm this will in fact enroll the learner in the course.

- Redeem endpoint

http://localhost:8002/coupons/redeem/?code=

This endpoint actually performs the code redemption by adding the associated course to
the learner's basket, applying the offer and completing the order.  This endpoint requires registration / login
and the learner will be presented with the login / registration view if not already logged in.
Once the order is complete the learner is redirected to the LMS dashboard where they can
see the course they just enrolled in.
