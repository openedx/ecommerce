Feature Toggling
================

All new features/functionality should be released behind a feature gate. This allows us to easily disable features
in the event that an issue is discovered in production. This project uses the
`Waffle <http://waffle.readthedocs.org/en/latest/>`_ library for feature gating.

Waffle supports three types of feature gates (listed below). We typically use flags and switches since samples are
random and not ideal for our needs.

    Flag
        Enable a feature for specific users, groups, users meeting certain criteria (e.g. authenticated or staff),
        or a certain percentage of visitors.

    Switch
        Simple boolean, toggling a feature for all users.

    Sample
        Toggle the feature for a specified percentage of the time.


For information on creating or updating features, refer to the
`Waffle documentation <http://waffle.readthedocs.org/en/latest/>`_.

Available Switches
------------------

Switches can be managed via the Django admin. The following switches exist:

+--------------------------------+---------------------------------------------------------------------------+
| Name                           | Functionality                                                             |
+================================+=======================+===================================================+
| user_enrollments_on_dashboard  | Display a user's current enrollments on the dashboard user detail page    |
+--------------------------------+---------------------------------------------------------------------------+
| publish_course_modes_to_lms    | Publish prices and SKUs to the LMS after every course modification        |
+--------------------------------+---------------------------------------------------------------------------+
| async_order_fulfillment        | Fulfill orders asynchronously                                             |
+--------------------------------+---------------------------------------------------------------------------+
| ENABLE_CREDIT_APP              | Enable the credit checkout page, from which students can purchase credit  |
|                                | courses                                                                   |
+--------------------------------+---------------------------------------------------------------------------+
| ENABLE_NOTIFICATIONS           | Enable email notifications for a variety of user actions (e.g., order     |
|                                | placed)                                                                   |
+--------------------------------+---------------------------------------------------------------------------+
| PAYPAL_RETRY_ATTEMPTS          | Enable retry mechanism for failed PayPal payment executions               |
+--------------------------------+---------------------------------------------------------------------------+

Business Intelligence (Analytics)
---------------------------------

We use `Segment <https://segment.com/>`_ to collect business intelligence data. Specify a value for ``SEGMENT_KEY`` in settings to emit events to the corresponding Segment project.

Permanent Feature Rollout
-------------------------
Over time some features may become permanent and no longer need a feature gate around them. In such instances, the
relevant code and tests should be updated to remove the feature gate. Once the code is released, the feature flag/switch
should be deleted.
