.. _Gating ECommerce Features:

####################################
Gating E-Commerce Service Features
####################################

You can release new E-Commerce service features and functionality behind a
feature gate. This project uses the `Waffle <http://waffle.readthedocs.org/en/latest>`_ library for feature gating.

****************************
Types of Feature Gates
****************************

Waffle supports the following types of feature gates.

* Flag: This gate allows you to enable a feature for specific users, groups,
  users who meet certain criteria (such as authenticated users or staff), or a
  certain percentage of visitors.

* Switch: This gate is a Boolean that turns a feature on or off for all
  users.

* Sample: This gate allows you to define the probability with which a given
  feature will be on.

For more information about creating or updating features and feature gates, see
the `Waffle documentation <http://waffle.readthedocs.org/en/latest>`_.

***************
Feature Gates
***************

Waffle offers the following feature gates.

.. list-table::
   :widths: 35 10 60
   :header-rows: 1

   * - Name
     - Type
     - Purpose
   * - user_enrollments_on_dashboard
     - Switch
     - Display a user's current enrollments on the dashboard user detail page.
   * - publish_course_modes_to_lms
     - Switch
     - Publish prices and SKUs to the LMS after every course modification.
   * - async_order_fulfillment
     - Sample
     - Specify what percentage of orders are fulfilled asynchronously.
   * - ENABLE_CREDIT_APP
     - Switch
     - Enable the credit checkout page, from which learners can purchase credit
       in a course.
   * - ENABLE_NOTIFICATIONS
     - Switch
     - Enable email notifications for a variety of user actions, such as when
       an order is placed.
   * - PAYPAL_RETRY_ATTEMPTS
     - Switch
     - Enable users to retry unsuccessful PayPal payments.
   * - allow_missing_lms_user_id
     - Switch
     - Allow a missing LMS user id without raising a MissingLmsUserIdException. For background, see
       `0004-unique-identifier-for-users <https://github.com/openedx/ecommerce/blob/master/docs/decisions/0004-unique-identifier-for-users.rst>`_
   * - disable_redundant_payment_check_for_mobile
     - Switch
     - Enable returning an error for duplicate transaction_id for mobile in-app purchases.
   * - enable_stripe_payment_processor
     - Flag
     - Ignore client side payment processor setting and use Stripe. For background, see `frontend-app-payment 0005-stripe-custom-actions <https://github.com/openedx/frontend-app-payment/blob/master/docs/decisions/0005-stripe-custom-actions.rst>`_.
   * - redirect_with_waffle_testing_querystring
     - Flag
     - Appends waffle flag value to MFE redirect URL's querystring.

**********************************
Enable a Feature Permanently
**********************************

If you want to make a feature permanent, remove its feature gate from relevant
code and tests, and delete the gate from the database.
