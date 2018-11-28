2. Use Custom Applicator for Applying Offers
------------------------------------------------------------

Status
------

Ran away

Context
-------

When a learner has wants to purchase a specific set of courses known as a program, the learner should get a discount.
To get this discount in Oscar, an `offer` is applied via the Applicator to the `basket` which contains the courses. The
`default behaviour of Oscar`_ is to look for all offers available in the system, and then attempt to apply each offer if
the offer fulfills the requirements of the basket.

.. _default behaviour of Oscar: https://github.com/django-oscar/django-oscar/blob/master/src/oscar/apps/offer/applicator.py#L50-L52

Decision
--------

Rather than attempting to apply every offer to a basket, we should override the `get_site_offers` method in the
Applicator class as recommended by Oscar.

Consequences
------------



References
----------
