.. _Tracking Data:

###################
Tracking Data
###################

The E-Commerce service uses `Segment <https://segment.com/>`_ to collect business intelligence data.

To emit events to your Segment project, specify your Segment project's API key
as the value of the ``SEGMENT_KEY`` setting.

UTM Data
--------

UTM data can be used for additional tracking information as follows:

* UTM data, when applicable, is recorded as basket attributes.

* A UTM cookie is used, which can be set using a variety of tools, like Google Tag Manager.

* Redirects to the payment page retain utm parameters.
