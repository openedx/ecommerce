Feature Toggling
================
All new features/functionality should be released behind a feature gate. This allows us to easily disable features
in the event that an issue is discovered in production. This project uses the
`Waffle <http://waffle.readthedocs.org/en/latest/>`_ library for feature gating.

Waffle supports three types of feature gates (listed below). We typically use flags and switches since samples are
random, and not ideal for our needs.

    Flag
        Enable a feature for specific users, groups, users meeting certain criteria (e.g. authenticated or staff),
        or a certain percentage of visitors.

    Switch
        Simple boolean, toggling a feature for all users.

    Sample
        Toggle the feature for a specified percentage of the time.


For information on creating or updating features, refer to the
`Waffle documentation <http://waffle.readthedocs.org/en/latest/>`_.

Permanent Feature Rollout
-------------------------
Over time some features may become permanent and no longer need a feature gate around them. In such instances, the
relevant code and tests should be updated to remove the feature gate. Once the code is released, the feature flag/switch
should be deleted.
