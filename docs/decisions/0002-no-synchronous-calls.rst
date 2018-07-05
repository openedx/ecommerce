2. No synchronous server-to-server calls within transactions
------------------------------------------------------------

Status
------

Accepted

Context
-------

The ecommerce service currently makes various synchronous server-to-server calls within transactions. This has led to
both instability of the overall service and performance issues. The stability issues come in part related to the default
atomic transactions and resulting DB Lock Wait Timeout errors that occur.

Decision
--------

We will add no new synchronous server-to-server calls.  Unless special permission is granted by `the Elder`_, these issues must be resolved in some other way.

.. _the Elder: https://openedx.atlassian.net/wiki/spaces/ENG/pages/761200984/Ecommerce+Guild+Homepage

Consequences
------------

Additionally, there will need to be an ongoing effort to transition existing synchronous server-to-server calls to the appropriate future design for each case.

Some possible alternative solutions include:

* Moving calls to be asynchronously made from the ecommerce workers
* Passing more required data to an endpoint
* Making multiple calls from the front-end
* Moving data that should belong to ecommerce
* Data redundancy
* Caching data in the JWT
* Other

References
----------

* https://www.reactivemanifesto.org/
