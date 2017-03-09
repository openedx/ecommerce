.. _Create Products Overview:

###########################
Creating Products Overview
###########################

.. include:: ../products_desc.txt

******************************
Prepare to Create a Product
******************************

Before you create a product, complete the following steps to start the
E-Commerce service on your site.

#. In the ecommerce and LMS configuration files (``/edx/etc/ecommerce.yml`` and
   ``/edx/app/edxapp/lms.auth.json``, respectively), verify the following
   settings.

   .. note::
    If you are using `devstack`_, these values are set correctly for you.
    However, edX recommends that you verify these values.

   * The ``EDX_API_KEY`` value in the LMS file must be the same as the
     ``EDX_API_KEY`` value in the ecommerce file. If the values differ, change
     the value in the LMS file to match the ecommerce file.
   * The ``ECOMMERCE_API_SIGNING_KEY`` value in the LMS file must be the same
     as the ``JWT_SECRET_KEY`` value in the ecommerce file. If the values
     differ, change the value in the LMS file to match the ecommerce file.

#. On devstack, start the E-Commerce server on port 8002, and start the LMS
   on port 8000.


.. include:: ../links/links.rst
