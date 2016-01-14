Feature Toggling
================

All new features/functionality should be released behind a feature gate. This allows us to release
new features in a controlled manner and easily disable features in the event that an issue is discovered
in production. This project uses the `Waffle <http://waffle.readthedocs.org/en/latest/>`_ library
for feature gating.

Waffle supports three types of feature gates, listed below.

    Flag
        Enable a feature for specific users, groups, users meeting certain criteria (e.g. authenticated or staff),
        or a certain percentage of visitors.

    Switch
        Simple boolean, toggling a feature for all users.

    Sample
        Toggle the feature for a specified percentage of the time.


For information on creating or updating features, refer to the
`Waffle documentation <http://waffle.readthedocs.org/en/latest/>`_.

Available Feature Gates
-----------------------

Waffle-based feature gates can be managed via the Django admin. The following feature gates exist:

============================= ====== ===============================================================================
Name                          Type   Purpose
============================= ====== ===============================================================================
user_enrollments_on_dashboard Switch Display a user's current enrollments on the dashboard user detail page
publish_course_modes_to_lms   Switch Publish prices and SKUs to the LMS after every course modification
async_order_fulfillment       Sample Determines what percentage of orders are fulfilled asynchronously.
ENABLE_CREDIT_APP             Switch Enable the credit checkout page, from which students can purchase credit course
ENABLE_NOTIFICATIONS          Switch Enable email notifications for a variety of user actions (e.g., order placed)
PAYPAL_RETRY_ATTEMPTS         Switch Enable retry mechanism for failed PayPal payment executions
============================= ====== ===============================================================================

Toggling Payment Processors
---------------------------

Payment processors sometimes experience temporary outages. When these outages occur, you can use Waffle switches to disable the faulty payment processor(s), then re-enable them after the outage is over.

The names of these switches are prefixed with the value of the setting ``PAYMENT_PROCESSOR_SWITCH_PREFIX``. By default, this value is ``payment_processor_active_``. The table below lists valid switches and the payment processors they control.

================= ==================================== =============
Payment Processor Switch Name                          Default Value
================= ==================================== =============
PayPal            payment_processor_active_paypal      True
CyberSource       payment_processor_active_cybersource True
================= ==================================== =============

The LMS is equipped to deal with the unlikely event that all payment processors are disabled.

Business Intelligence (Analytics)
---------------------------------

We use `Segment <https://segment.com/>`_ to collect business intelligence data. Specify a value for ``SEGMENT_KEY`` in settings to emit events to the corresponding Segment project.

Permanent Feature Rollout
-------------------------
Over time some features may become permanent and no longer need a feature gate around them. In such instances, the
relevant code and tests should be updated to remove the feature gate. Once the code is released, the feature flag/switch
should be deleted.
