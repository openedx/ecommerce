6. Use Custom Applicator Throughout Ecommerce
------------------------------------------------------------

Status
------

Accepted

Context
-------

Oscar uses an Applicator object to apply offers to a basket.  The `default behaviour of Oscar Applicator`_ is to look for all offers available in the system, and then attempt to apply each offer that fulfills the requirements of the basket.

This default behavior was causing performance issues by looking at many Program offers, when it was clear ahead of time that only 0 or 1 of them could possibly apply.

Additionally, after creating a `custom applicator`_ with our own logic, it provided different results than the default applicator.  When we did not use it consistently throughout the system, we saw bugs as different offers were applied by different part of the code base.

Decision
--------

This `custom applicator`_ will encapsulate business logic to prefilter the programs and enterprise offers first. Otherwise, gets the site offers not associated with any bundle or enterprise customer rather than blindly returning every offer, including ones that could never apply.

Rather than attempting to apply every offer to a basket, we should override the `get_site_offers()`_ method in the Applicator class as recommended by Oscar and use it throughout Ecommerce and django-oscar as default applicator.

This should be the only applicator used throughout Ecommerce including django-oscar that uses the configured applicator. Otherwise, we will have bugs as different offers are applied by different part of the code base. The `custom applicator`_ comments should be kept up to date with the full set of business logic decisions as needed.

Consequences
------------

Use the `custom applicator`_ as default applicator throughout Ecommerce and django-oscar, otherwise we will have bugs as different offers are applied by different code.

We noticed some bugs in which learners were seeing different prices and discounts on program about pages from actual basket page because we were using django-oscar applicator on calculate basket endpoint but the basket endpoint was using our `custom applicator`_. We also received some reports where no offer was applied on basket but the payment processor code applied an offer on the actual payment due to django-oscar applicator and learners were charged less then the actual price.


.. _default behaviour of Oscar Applicator: https://github.com/django-oscar/django-oscar/blob/40a4cacc27223ac675f5e859e7568b632e3f304c/src/oscar/apps/offer/applicator.py#L46-L61
.. _custom applicator: https://github.com/edx/ecommerce/blob/master/ecommerce/extensions/offer/applicator.py
.. _get_site_offers(): https://github.com/django-oscar/django-oscar/blob/40a4cacc27223ac675f5e859e7568b632e3f304c/src/oscar/apps/offer/applicator.py#L63-L72
