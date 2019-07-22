/**
 * CyberSource payment processor specific actions.
 */
define([
    'jquery',
    'js-cookie',
    'underscore.string',
    'pages/basket_page'
], function($, Cookies, _s, BasketPage) {
    'use strict';

    return {
        init: function(config) {
            var $paymentForm = $('#paymentForm'),
                $pciFields = $('.pci-field', $paymentForm),
                cardMap = {
                    visa: '001',
                    mastercard: '002',
                    amex: '003',
                    discover: '004'
                };

            this.signingUrl = config.signingUrl;

            // The payment form should post to CyberSource
            $paymentForm.attr('action', config.postUrl);

            // Add name attributes to the PCI fields
            $pciFields.each(function() {
                var $this = $(this);
                $this.attr('name', $this.data('name'));
            });

            $paymentForm.submit($.proxy(this.onSubmit, this));

            // Add CyberSource-specific fields
            $paymentForm.append($('<input type="hidden" name="card_expiry_date" class="pci-field">'));
            $paymentForm.append($('<input type="hidden" name="card_type" class="pci-field">'));

            // Add an event listener to populate the CyberSource card type field
            $paymentForm.on('cardType:detected', function(event, data) {
                $('input[name=card_type]', $paymentForm).val(cardMap[data.type]);
            });

            this.applePayConfig = config.applePay;
            this.initializeApplePay();
        },

        /**
         * Payment form submit handler.
         *
         * Before posting to CyberSource, this handler retrieves signed data fields from the server. PCI fields
         * (e.g. credit card number, expiration) should NEVER be posted to the server, only to CyberSource.
         *
         * @param event
         */
        onSubmit: function(event) {
            var $form = $(event.target),
                $signedFields = $('input,select', $form).not('.pci-field'),
                expMonth = $('#card-expiry-month', $form).val(),
                expYear = $('#card-expiry-year', $form).val();

            // Restore name attributes so the data can be posted to CyberSource
            $('#card-number', $form).attr('name', 'card_number');
            $('#card-cvn', $form).attr('name', 'card_cvn');

            // Post synchronously since we need the returned data.
            $.ajax({
                type: 'POST',
                url: this.signingUrl,
                data: $signedFields.serialize(),
                async: false,
                success: function(data) {
                    var formData = data.form_fields,
                        key;

                    // Format the date for CyberSource (MM-YYYY)
                    $('input[name=card_expiry_date]', $form).val(expMonth + '-' + expYear);

                    // Disable the fields on the form so they are not posted since their names are not what is
                    // expected by CyberSource. Instead post add the parameters from the server to the form,
                    // and post them.
                    $signedFields.attr('disabled', 'disabled');

                    // eslint-disable-next-line no-restricted-syntax
                    for (key in formData) {
                        if (Object.prototype.hasOwnProperty.call(formData, key)) {
                            $form.append(
                                '<input type="hidden" name="' + key + '" value="' + formData[key] + '" />'
                            );
                        }
                    }
                },

                error: function(jqXHR, textStatus) {
                    var $field,
                        cardHolderFields,
                        error,
                        k;

                    // Don't allow the form to submit.
                    event.preventDefault();
                    event.stopPropagation();

                    cardHolderFields = [
                        'first_name', 'last_name', 'address_line1', 'address_line2', 'state', 'city', 'country',
                        'postal_code'
                    ];

                    if (textStatus === 'error') {
                        error = JSON.parse(jqXHR.responseText);

                        if (error.field_errors) {
                            // eslint-disable-next-line no-restricted-syntax
                            for (k in error.field_errors) {
                                if (cardHolderFields.indexOf(k) !== -1) {
                                    $field = $('input[name=' + k + ']');
                                    // TODO Use custom events to remove this dependency.
                                    BasketPage.appendCardHolderValidationErrorMsg($field, error.field_errors[k]);
                                    $field.focus();
                                }
                            }
                        } else {
                            // Unhandled errors should redirect to the general payment error page.
                            window.location.href = window.paymentErrorPath;
                        }
                    }
                }
            });
        },

        displayErrorMessage: function(message) {
            $('#messages').html(_s.sprintf('<div class="alert alert-error">%s<i class="icon-warning-sign"></i></div>',
                message));
        },

        initializeApplePay: function() {
            var promise,
                self = this;

            if (window.ApplePaySession && self.applePayConfig.enabled) {
                // eslint-disable-next-line no-undef
                promise = new Promise(function(resolve) {
                    if (ApplePaySession.canMakePayments()) {
                        resolve(true);
                    }
                    resolve(false);
                });

                promise.then(
                    function(canMakePayments) {
                        var applePayBtn = document.getElementById('applePayBtn');

                        if (canMakePayments) {
                            console.log('Learner is eligible for Apple Pay');   // eslint-disable-line no-console

                            // Display the button
                            applePayBtn.style.display = 'inline-flex';
                            applePayBtn.addEventListener('click', self.onApplePayButtonClicked.bind(self));
                        } else {
                            console.log('Apple Pay not setup.');   // eslint-disable-line no-console
                        }
                    }
                );

                return promise;
            }

            // Return an empty promise for callers expecting a promise (e.g. tests). If Promise is not supported the
            // browser (e.g. Internet Explorer), return nothing.
            /* istanbul ignore next */
            if (typeof Promise !== 'undefined') {
                // eslint-disable-next-line no-undef
                return Promise.resolve();
            }

            /* istanbul ignore next */
            return null;
        },

        onApplePayButtonClicked: function(event) {
            // Setup the session and its event handlers
            this.applePaySession = new ApplePaySession(2, {
                countryCode: this.applePayConfig.countryCode,
                currencyCode: this.applePayConfig.basketCurrency,
                supportedNetworks: ['amex', 'discover', 'visa', 'masterCard'],
                merchantCapabilities: ['supports3DS', 'supportsCredit', 'supportsDebit'],
                total: {
                    label: this.applePayConfig.merchantName,
                    type: 'final',
                    amount: this.applePayConfig.basketTotal
                },
                requiredBillingContactFields: ['postalAddress']
            });

            this.applePaySession.onvalidatemerchant = this.onApplePayValidateMerchant.bind(this);
            this.applePaySession.onpaymentauthorized = this.onApplePayPaymentAuthorized.bind(this);

            // Let's start the show!
            this.applePaySession.begin();

            event.preventDefault();
            event.stopPropagation();
        },

        onApplePayValidateMerchant: function(event) {
            var self = this;
            console.log('Validating merchant...');   // eslint-disable-line no-console

            $.ajax({
                method: 'POST',
                url: this.applePayConfig.startSessionUrl,
                headers: {
                    'X-CSRFToken': Cookies.get('ecommerce_csrftoken')
                },
                data: JSON.stringify({url: event.validationURL}),
                contentType: 'application/json',
                success: function(data) {
                    console.log('Merchant validation succeeded.');   // eslint-disable-line no-console
                    console.log(data);   // eslint-disable-line no-console
                    self.applePaySession.completeMerchantValidation(data);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    // Translators: Do not translate "Apple Pay".
                    var msg = gettext('Apple Pay is not available at this time. Please try another payment method.');

                    console.log('Merchant validation failed!');   // eslint-disable-line no-console
                    console.log(textStatus);   // eslint-disable-line no-console
                    console.log(errorThrown);   // eslint-disable-line no-console

                    self.applePaySession.abort();
                    self.displayErrorMessage(msg);
                }
            });
        },

        onApplePayPaymentAuthorized: function(event) {
            var self = this;
            console.log('Submitting Apple Pay payment to CyberSource...');   // eslint-disable-line no-console

            $.ajax({
                method: 'POST',
                url: this.applePayConfig.authorizeUrl,
                headers: {
                    'X-CSRFToken': Cookies.get('ecommerce_csrftoken')
                },
                data: JSON.stringify(event.payment),
                contentType: 'application/json',
                success: function(data) {
                    console.log(data);   // eslint-disable-line no-console
                    self.applePaySession.completePayment(ApplePaySession.STATUS_SUCCESS);
                    self.redirectToReceipt(data.number);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    var msg = gettext('An error occurred while processing your payment. You have NOT been charged. ' +
                        'Please try again, or select another payment method.');

                    console.log(textStatus);   // eslint-disable-line no-console
                    console.log(errorThrown);   // eslint-disable-line no-console
                    self.applePaySession.completePayment(ApplePaySession.STATUS_FAILURE);
                    self.displayErrorMessage(msg);
                }
            });
        },

        /* istanbul ignore next */
        redirectToReceipt: function(orderNumber) {
            /* istanbul ignore next */
            window.location.href = this.applePayConfig.receiptUrl + '?order_number=' + orderNumber;
        }
    };
});
