Maintenance
===========
Most installations should not require any maintenance beyond patching; however, there are a few exceptions.

Baskets
~~~~~~~
As more baskets and orders are created, the baskets table can grow pretty large. Depending on your database backend, a
large table can become difficult to manage and migrate. Once an order is placed, the corresponding basket doesn't hold
much value and can be deleted. The `delete_ordered_baskets` management command performs this action.

.. code-block:: bash

    # Display number of baskets eligible for deletion
    $ ./manage.py delete_ordered_baskets

    # Delete all baskets that have been ordered
    $ ./manage.py delete_ordered_baskets --commit
