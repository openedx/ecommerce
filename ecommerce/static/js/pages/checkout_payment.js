/**
 * Checkout payment page scripts.
 **/

require([
        'jquery',
        'underscore',
        'jquery-cookie'
    ],
    function ($,
              _) {
        'use strict';

        var redirectToPaymentProvider = function (data) {
            var $form = $('<form>', {
                action: data.payment_page_url,
                method: 'POST',
                'accept-method': 'UTF-8'
            });

            _.each(data.payment_form_data, function (value, key) {
                $('<input>').attr({
                    type: 'text',
                    name: key,
                    value: value
                }).appendTo($form);
            });

            $form.submit();
        };

        $(document).ready(function () {
            var $paymentButtons = $('.payment-buttons'),
                basketId = $paymentButtons.data('basket-id');

            $paymentButtons.find('.payment-button').click(function (e) {
                var $btn = $(e.target),
                    paymentProcessor = $btn.val(),
                    data = {
                        basket_id: basketId,
                        payment_processor: paymentProcessor
                    };

                $.ajax({
                    url: '/api/v2/checkout/',
                    type: 'POST',
                    contentType: 'application/json; charset=utf-8',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': $.cookie('ecommerce_csrftoken')
                    },
                    data: JSON.stringify(data)
                }).done(function (data, textStatus, jqXHR) {
                    redirectToPaymentProvider(data);
                });
            });
        });
    }
);
