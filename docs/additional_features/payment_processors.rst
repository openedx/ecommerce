Payment Processors
##################
Payment processors/gateways handle the acceptance/validation of payment data--credit cards, wallet payments, etc.--and
transfer of funds from learners to merchants. At edx.org, we use CyberSource to accept credit card payments, and PayPal
to accept PayPal payments (made from either the learner's PayPal account, bank account, or credit card).

If you are interested in supporting another payment processor, reach out to the open source community to determine if
someone has already developed an integration. Otherwise, you may refer to existing integrations as reference points.

All processor secrets are configured via the ``PAYMENT_PROCESSOR_CONFIG`` setting. This is a `dict` that maps partner
short codes to another dict that maps processor names to configuration. These settings are for each site/tenant. In
order to make use of a processor, the processor needs to be activated via the Site Configuration Django admin form.
Finally, there are Waffle flags that can be used to disable payment processors for all tenants in the event of an outage.

.. note::

    The payment processor settings below will be displayed as if they were defined in a Python settings file. Ideally,
    you should use the Ansible plays in edx/configuration to generate the settings, however that may not feasible for
    those using pre-built systems such as the EC2 images from Bitnami and other providers.


Disabling Payment Processors
****************************
Payment processors sometimes experience temporary outages. When these outages occur, you can use Waffle switches to
disable the faulty payment processor or processors, then re-enable them after the outage is over.

The names of these switches use prefixes that are the value of the ``PAYMENT_PROCESSOR_SWITCH_PREFIX`` setting. By
default, this value is ``payment_processor_active_``. The following table lists valid switches and the payment
processors they control.

.. list-table::
   :header-rows: 1

   * - Payment Processor
     - Switch Name
     - Default Value
   * - PayPal
     - payment_processor_active_paypal
     - True
   * - CyberSource
     - payment_processor_active_cybersource
     - True

In the unlikely event that all payment processors are disabled, the LMS will display an informative error message
explaining why payment is not currently possible.


Apple Pay
*********
Apple Pay allows learners to checkout quickly without having to manually fill out the payment form. If you are not
familiar with Apple Pay, please take a moment to read the following documents to understand the user flow and necessary
configuration. **Apple Pay support is only available when using the CyberSource processor.**

* `Apple Pay JS <https://developer.apple.com/documentation/applepayjs>`_
* `CyberSource: Apple Pay Using  the Simple Order API <https://www.cybersource.com/developers/integration_methods/apple_pay/>`_

Apple Pay is only available to learners using Safari on the following platforms:

* iOS 10+ on devices with a Secure Element
* macOS 10.12+. The user must have an iPhone, Apple Watch, or a MacBook Pro with Touch ID that can authorize the
  payment.

An exhaustive list of devices that support Apple Pay is available on
`Wikipedia <https://en.wikipedia.org/wiki/Apple_Pay>`_.

.. note::

    The Apple Pay button is not displayed to users with incompatible hardware and software.


CyberSource
***********
Our CyberSource integration supports accepting payments via both `Silent Order POST and Secure Acceptance Web/Mobile`_.
(Note that both fall under the product name of "Secure Acceptance".) We highly recommend using the Silent Order POST
integration as it allows for greater control over the checkout experience via the use of the custom checkout page in
this codebase. Web/Mobile, on the other hand, redirects learners to a checkout page hosted by CyberSource.

In addition to Secure Acceptance, this processor plugin also makes use of the `Simple Order API`_ to facilitate payments
made via Apple Pay and refunds (for all payment methods).

When testing payments with your test profiles, use test card numbers from https://www.cybersource.com/developers/other_resources/quick_references/test_cc_numbers/.

.. _Silent Order POST and Secure Acceptance Web/Mobile: https://www.cybersource.com/products/payment_security/secure_acceptance_web_mobile/
.. _Simple Order API: https://www.cybersource.com/developers/integration_methods/simple_order_and_soap_toolkit_api/


Settings
--------
Note that "EBC" below refers to the Business Center accessible at one of the two URLs below, depending on the
environment in which you are operating.

* Test: https://ebctest.cybersource.com/ebctest/login/Login.do
* Production: https://ebc.cybersource.com/ebc/login/Login.do

.. code-block:: python

    # PAYMENT_PROCESSOR_CANCEL_PATH and PAYMENT_PROCESSOR_ERROR_PATH should come from here
    from ecommerce.settings.production import *

    PAYMENT_PROCESSOR_CONFIG = {
        'edx': {
            'cybersource': {
                # This is the merchant ID assigned by CyberSource
                'merchant_id': '',

                # Generate this at EBC: Account Management > Transaction Security Keys > SOAP Toolkit API
                'transaction_key': '',

                # Production: https://ics2wsa.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl
                'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl',

                # Use the default value in settings/base.py or Ansible
                'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,

                # This instructs the plugin to send Level II/III details. Consider disabling if you run into issues.
                'send_level_2_3_details': True,

                # Generate this at EBC: Tools & Settings > Profiles.
                # Remember to select "Silent Order Post" as your integration method!
                'sop_profile_id': '',
                'sop_access_key': '',
                'sop_secret_key': '',

                # Production: https://secureacceptance.cybersource.com/silent/pay
                'sop_payment_page_url': 'https://testsecureacceptance.cybersource.com/silent/pay',

                # These come from the Apple Developer portal
                # https://developer.apple.com/account/ios/identifier/merchant
                'apple_pay_merchant_identifier': '',
                'apple_pay_merchant_id_domain_association': '',

                # Two-letter ISO 3166 country code for your business/merchant account
                # https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
                'apple_pay_country_code': '',

                # Filesystem path to the merchant identity certificate (used to authenticate with Apple to start
                # sessions). This file should be kept in a secure location that is only accessible by administrators
                # and the application' service user.
                'apple_pay_merchant_id_certificate_path': '',
            },
        },
    }


PayPal
******
The PayPal integration redirects learners to a PayPal checkout page where they can pay with a PayPal balance, bank
transfer, or credit card. Regardless of how the learner pays, the work done by the E-Commerce Service is the same. In
fact, the service doesn't even know the payment method.


Settings
--------

.. code-block:: python

    # PAYMENT_PROCESSOR_CANCEL_PATH and PAYMENT_PROCESSOR_ERROR_PATH should come from here
    from ecommerce.settings.production import *

    PAYMENT_PROCESSOR_CONFIG = {
        'edx': {
            'paypal': {
                # Change this to 'live' in production
                'mode': 'sandbox',

                # These credentials come from PayPal at https://developer.paypal.com/.
                'client_id': '',
                'client_secret': '',

                # Use the default value in settings/base.py or Ansible
                'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
                'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
            },
        },
    }
