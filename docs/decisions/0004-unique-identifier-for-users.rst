4. Unique Identifiers for Users
-------------------------------

Status
------

Accepted

Context
-------

In support of *OEP-32: Unique Identifier for Users*, Ecommerce should be able to retrieve the unique identifier for
each user in Ecommerce's database.

Decision
--------

A column named *lms_user_id* was added to the *ecommerce_user* table in Ecommerce's database. This column now contains
the unique user id (aka LMS user id).

Incoming requests to Ecommerce that include a JWT now save the LMS user id during JWT Authentication; see
*JWT_PAYLOAD_USER_ATTRIBUTE_MAPPING*.

In addition, middleware now checks to see if the user is missing an LMS user id. If the id is missing, the middleware
retrieves it from the user's social auth. If multiple social auth rows are found for the user, the most recently
saved row is used.

To back-fill the LMS user id for existing users, run the `import_user_ids <https://github.com/edx/ecommerce/blob/master/ecommerce/core/management/commands/import_user_ids.py>`_
management command.

New users receive an LMS user id in the ecommerce database as part of the JWT and/or social auth flow once they login
via the LMS and interact with ecommerce by, for example, adding a course to their basket.

Consequences
------------

The LMS user id is expected to be be present for every user is Ecommerce's database, and this id is included in
analytics data that is sent out from Ecommerce.

Requests that are sent to Ecommerce are expected to include the LMS user id. If they do not include the id, the
creator of the request is responsible for ensuring that Ecommerce already knows the LMS user id for the user. Requests
to Ecommerce will be rejected and a MissingLmsUserIdException will be raised if Ecommerce cannot find a LMS user id for
the affected user(s), unless the *allow_missing_lms_user_id* waffle switch is enabled.

References
----------

* https://github.com/edx/open-edx-proposals/blob/master/oeps/oep-0032-arch-unique-identifier-for-users.rst
