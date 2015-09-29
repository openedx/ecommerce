Notifications
=============

We use Oscar's `Communications API <http://django-oscar.readthedocs.org/en/latest/howto/how_to_customise_oscar_communications.html#communications-api>`_ to create and send email notifications. If you've enabled the feature, you may define arbitrary "Communication Type Codes" used to refer to particular types of notification. For example, the Communication Type Code corresponding to the purchase of a course seat might be ``COURSE_SEAT_PURCHASED``.

Each email requires the presence of three files: an HTML template, a plain text file containing the email's subject line, and a plain text file containing the email's body. The files should be placed in ``ecommerce/ecommerce/templates/customer/emails/``. You should adhere to the following naming convention: ``commtype_{Communication Type Code}_body.html``. For example, an email related to the purchase of a course seat should have template file named ``commtype_course_seat_purchased_body.html``, ``commtype_course_seat_purchased_body.txt``, and ``commtype_course_seat_purchased_subject.txt``. The HTML template should extend ``email_base.html``. Override ``block body`` to add a custom email body and, optionally, ``block footer`` to add a custom footer.

To actually send emails, use the method ``send_notification(user, commtype_code, context)``, implemented in ``ecommerce/ecommerce/notifications/notifications.py``.
