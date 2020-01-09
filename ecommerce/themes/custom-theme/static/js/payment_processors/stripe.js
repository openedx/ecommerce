/**
 * Stripe payment processor specific actions.
 */
define([
    'jquery',
    'underscore.string'
], function($, _s) {
    'use strict';

    return {
        init: function(config) {
            this.publishableKey = config.publishableKey;
            this.postUrl = config.postUrl;
            this.$paymentForm = $('#paymentForm');
            this.stripe = Stripe(this.publishableKey);
            this.paymentRequestConfig = {
                country: config.country,
                currency: config.paymentRequest.currency,
                total: {
                    label: config.paymentRequest.label,
                    amount: config.paymentRequest.total
                }
            };

            // NOTE: We use Stripe v2 for credit card payments since v3 requires using Elements, which would force us
            // to make a custom payment form just for Stripe. Using v2 allows us to continue using the same payment form
            // regardless of the backend processor.
            Stripe.setPublishableKey(this.publishableKey);

            this.$paymentForm.on('submit', $.proxy(this.onPaymentFormSubmit, this));
            this.initializePaymentRequest();
        },

        onPaymentFormSubmit: function(e) {
            var data = {},
                fieldMappings = {
                    'card-number': 'number',
                    'card-expiry-month': 'exp_month',
                    'card-expiry-year': 'exp_year',
                    'card-cvn': 'cvc',
                    id_postal_code: 'address_zip',
                    id_address_line1: 'address_line1',
                    id_address_line2: 'address_line2',
                    id_city: 'address_city',
                    id_state: 'address_state',
                    id_country: 'address_country'
                },
                $paymentForm = $('#paymentForm');

            // Extract the form data so that it can be incorporated into our token request
            Object.keys(fieldMappings).forEach(function(id) {
                data[fieldMappings[id]] = $('#' + id, $paymentForm).val();
            });

            data.name = $('#id_first_name').val() + ' ' + $('#id_last_name').val();

            // Disable the submit button to prevent repeated clicks
            $paymentForm.find('#payment-button').prop('disabled', true);

            // Request a token from Stripe
            Stripe.card.createToken(data, $.proxy(this.onCreateCardToken, this));

            e.preventDefault();
        },

        onCreateCardToken: function(status, response) {
            var msg;

            if (response.error) {
                console.log(response.error.message);    // eslint-disable-line no-console
                msg = gettext('An error occurred while attempting to process your payment. You have not been ' +
                    'charged. Please check your payment details, and try again.') + '<br><br>Debug Info: ' +
                    response.error.message;
                this.displayErrorMessage(msg);
                this.$paymentForm.find('#payment-button').prop('disabled', false); // Re-enable submission
            } else {
                this.postTokenToServer(response.id);
            }
        },

        postTokenToServer: function(token, paymentRequest) {
            var self = this,
                formData = new FormData();

            formData.append('stripe_token', token);
            formData.append('csrfmiddlewaretoken', $('[name=csrfmiddlewaretoken]', self.$paymentForm).val());
            formData.append('basket', $('[name=basket]', self.$paymentForm).val());

            fetch(self.postUrl, {
                credentials: 'include',
                method: 'POST',
                body: formData
            }).then(function(response) {
                if (response.ok) {
                    if (paymentRequest) {
                        // Report to the browser that the payment was successful, prompting
                        // it to close the browser payment interface.
                        paymentRequest.complete('success');
                    }
                    response.json().then(function(data) {
                        window.location.href = data.url;
                    });
                } else {
                    if (paymentRequest) {
                        // Report to the browser that the payment failed, prompting it to re-show the payment
                        // interface, or show an error message and close the payment interface.
                        paymentRequest.complete('fail');
                    }

                    self.displayErrorMessage(gettext('An error occurred while processing your payment. ' +
                        'Please try again.'));
                }
            });
        },

        displayErrorMessage: function(message) {
            $('#messages').html(
                _s.sprintf(
                    '<div class="alert alert-error"><i class="icon fa fa-exclamation-triangle"></i>%s</div>',
                    message
                )
            );
        },

        initializePaymentRequest: function() {
            var self = this,
                paymentRequest = self.stripe.paymentRequest(this.paymentRequestConfig),
                elements = self.stripe.elements(),
                paymentRequestButton = elements.create('paymentRequestButton', {
                    paymentRequest: paymentRequest,
                    style: {
                        paymentRequestButton: {
                            height: '50px'
                        }
                    }
                });

            // Check the availability of the Payment Request API first.
            paymentRequest.canMakePayment().then(function(result) {
                if (result) {
                    paymentRequestButton.mount('#payment-request-button');
                } else {
                    document.getElementById('payment-request-button').style.display = 'none';
                }
            });

            paymentRequest.on('token', function(ev) {
                self.postTokenToServer(ev.token.id, ev);
            });
        }
    };
});
