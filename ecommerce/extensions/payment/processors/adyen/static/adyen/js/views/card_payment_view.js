define([
        'jquery',
        'underscore',
        'backbone',
        'adyen/encrypt',
        'js-cookie',
        'bootstrap_validator'
    ],
    function ($,
              _,
              Backbone,
              AdyenEncrypt,
              Cookies
    ) {
        'use strict';

        return Backbone.View.extend({
            events: {
                'focus input': 'clearMessages'
            },

            initialize: function() {
                this.$el = $(this.el);
                this.$messages = this.$el.find('#payment-messages');
                this.paymentAuthorizationApiUrl = window.paymentAuthorizationApiUrl;
                // Add client-side encryption of payment details
                AdyenEncrypt.createEncryptedForm(this.el, window.adyenCSEPublicKey, {
                    onsubmit: $.proxy(this.submit, this)
                });
                // Add payment form validation
                this.$el.validator();
            },

            clearMessages: function(event) {
                this.$messages.empty();
            },

            handlePaymentResponse: function(data, status, xhr) {
                if (data.authorized) {
                    window.location.replace(this.$el.data('receipt-url'));
                } else {
                    this.$el.find('#payment-messages').empty().append(
                        '<div class="alert alert-danger fade in" role="alert">' +
                        '<div class="alertinner wicon">' +
                        'Sorry, your payment was not successful. ' +
                        'Please be sure your billing address and payment details are correct and try again.' +
                        '</div>' +
                        '</div>'
                    );
                    this.setPaymentEnabled(true);
                }
            },

            handlePaymentError: function(xhr, status, error) {
                // Unexpected error, redirect to error page
                window.location.replace(this.$el.data('error-url'));
            },

            setPaymentEnabled: function (isEnabled) {
                if (_.isUndefined(isEnabled)) {
                    isEnabled = true;
                }
                this.$el.find('button[type="submit"]')
                    .prop('disabled', !isEnabled)
                    .attr('aria-disabled', !isEnabled)
                    .button(isEnabled ? 'reset' : 'loading');
            },

            submit: function(event) {
                event.preventDefault();
                this.setPaymentEnabled(false);
                $.ajax({
                    url: this.paymentAuthorizationApiUrl,
                    method: 'POST',
                    data: this.$el.serializeArray(),
                    headers: {'X-CSRFToken': Cookies.get('ecommerce_csrftoken')},
                    context: this,
                    success: this.handlePaymentResponse,
                    error: this.handlePaymentError
                });
            }
        });
    });
