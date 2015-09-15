======================
Site Configuration
======================

This is a custom functionality since ``django-oscar`` doesn't offer this kind of configuration.
We have extended the `Django sites framework <https://docs.djangoproject.com/en/1.8/ref/contrib/sites/>`_ in order to add site-specific configuration.
The site's framework allows for the mapping of domains to a **Site** object which consists of an ID and a name.

The multi-tenant implementation has one site per partner.


---------------------------------------------
Site Configuration Model | Django Admin
---------------------------------------------

To add and update a custom site's configurations, including the basic theming and payment processor, use the ``SiteConfiguration`` model in the `Django administration panel <http://localhost:8002/admin/core/siteconfiguration/add>`_.
This panel is located at http://localhost:8002/admin/core/siteconfiguration/.

The following image shows the ``SiteConfiguration`` model in the Django administration panel for a configured site.

.. image:: images/site_configuration.png
    :width: 600px
    :alt: Populated site configuration model

.. note::  There is a **unique together** constraint on the **site** and **partner** fields for the ``SiteConfiguration`` model.
    This means that there can be only one entry per site per partner.

    Please make sure that there is only one partner per site.
