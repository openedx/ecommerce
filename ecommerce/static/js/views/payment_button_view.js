define([
        'jquery',
        'underscore',
        'backbone',
        'js-cookie'
    ],
    function ($,
              _,
              Backbone,
              Cookies
    ) {
        'use strict';

        return Backbone.View.extend({
            events: {
                'click .payment-button': 'checkout'
            },

            initialize: function () {
                _.bindAll(this, 'checkout');
                this.sku = null;
            },

            checkout: function (event) {
                var processor_name = $(event.currentTarget).data('processor-name'),
                    url = '/api/v2/baskets/',
                    postData = JSON.stringify({
                        'products': [{'sku': this.sku}],
                        'checkout': true,
                        'payment_processor_name': processor_name
                    });

                // Disable the payment button to prevent multiple submissions
                this.setPaymentEnabled(false);

                $.ajax({
                    url: url,
                    method: 'post',
                    contentType: 'application/json',
                    data: postData,
                    headers: {'X-CSRFToken': Cookies.get('ecommerce_csrftoken')},
                    context: this,
                    success: this.handleCreateOrderResponse,
                    error: this.handleCreateOrderError
                });
            },

            setPaymentEnabled: function (isEnabled) {
                if (_.isUndefined(isEnabled)) {
                    isEnabled = true;
                }
                $('.payment-button')
                    .toggleClass('is-disabled', !isEnabled)
                    .prop('disabled', !isEnabled)
                    .attr('aria-disabled', !isEnabled);
            },

            handleCreateOrderResponse: function (paymentDataResponse) {
                // At this point, the basket has been created on the server,
                // and we've received signed payment parameters.
                // We need to dynamically construct a form using
                // these parameters, then submit it to the payment processor.
                // This will send the user to an externally-hosted page
                // where she can proceed with payment.
                var paymentData = paymentDataResponse.payment_data,
                    form = $('#payment-processor-form');

                $('input', form).remove();

                form.attr('action', paymentData.payment_page_url);
                form.attr('method', 'POST');

                _.each(paymentData.payment_form_data, function (value, key) {
                    $('<input>').attr({
                        type: 'hidden',
                        name: key,
                        value: value
                    }).appendTo(form);
                });

                this.submitForm(form);
            },

            submitForm: function (form) {
                form.submit();
            },

            handleCreateOrderError: function (xhr) {
                var errorMsg = gettext('An error has occurred. Please try again.');

                if (xhr.status === 400) {
                    errorMsg = xhr.responseText;
                }

                // Re-enable the button so the user can re-try
                this.setPaymentEnabled(true);
            },

            setSku: function (sku) {
                this.sku = sku;
            }
        });
    });
