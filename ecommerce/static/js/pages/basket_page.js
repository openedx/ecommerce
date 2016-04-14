/**
 * Basket page scripts.
 **/

define([
        'jquery',
        'underscore',
        'underscore.string',
        'utils/utils',
        'utils/analytics_utils',
    ],
    function ($,
              _,
              _s,
              Utils,
              AnalyticsUtils) {
        'use strict';

        var appendToForm = function (value, key, form) {
            $('<input>').attr({
                type: 'text',
                name: key,
                value: value
            }).appendTo(form);
        },
        checkoutPayment = function(data) {
            $.ajax({
                url: '/api/v2/checkout/',
                method: 'POST',
                contentType: 'application/json; charset=utf-8',
                dataType: 'json',
                headers: {
                    'X-CSRFToken': $.cookie('ecommerce_csrftoken')
                },
                data: JSON.stringify(data),
                success: onSuccess,
                error: onFail
            });
        },
        hideVoucherForm = function() {
            $('#voucher_form_container').hide();
            $('#voucher_form_link').show();
        },
        onFail = function(){
            var message = gettext('Problem occurred during checkout. Please contact support');
            $('#messages').empty().append(
                _s.sprintf('<div class="error">%s</div>', message)
            );
        },
        onSuccess = function (data) {
            var $form = $('<form>', {
                class: 'hidden',
                action: data.payment_page_url,
                method: 'POST',
                'accept-method': 'UTF-8'
            });

            _.each(data.payment_form_data, function (value, key) {
                    $('<input>').attr({
                        type: 'hidden',
                        name: key,
                        value: value
                    }).appendTo($form);
                  });

            $form.appendTo('body').submit();
        },
        onReady = function() {
            var $paymentButtons = $('.payment-buttons'),
                basketId = $paymentButtons.data('basket-id');

            $('#voucher_form_link a').on('click', function(event) {
                event.preventDefault();
                showVoucherForm();
            });

            $('#voucher_form_cancel').on('click', function(event) {
                event.preventDefault();
                hideVoucherForm();
            });

            $("input[id^=quantity_]").on('change', function(event) {
                event.preventDefault();
                var $line = $(this),
                price = $line.data('line-price'),
                currency = $line.data('line-currency');

                //TODO: Currency symbol
                $line.closest('.col-sm-2').next().find('.price').text( (price * $line.val()) + currency);
                //TODO: can pass a ID to this price HTML tag
            });

            $paymentButtons.find('.payment-button').click(function (e) {
                var $btn = $(e.target),
                    deferred = new $.Deferred(),
                    promise = deferred.promise(),
                    paymentProcessor = $btn.val(),
                    data = {
                        basket_id: basketId,
                        payment_processor: paymentProcessor
                    };
                data = appendBasketItems(data);

                Utils.disableElementWhileRunning($btn, function() { return promise; });
                checkoutPayment(data);
            });

            AnalyticsUtils.analyticsSetUp();
        },
        showVoucherForm = function() {
            $('#voucher_form_container').show();
            $('#voucher_form_link').hide();
            $('#id_code').focus();
        },
        appendBasketItems = function(data) {
            data['seat_quantities'] = {};

            $("input[id^=quantity_]").each(function() {
                //Trim full id of field
                var $line = $(this), id = $line.attr('id').split('quantity_')[1];
                data['seat_quantities'][id] = $line.val();
            });
        };

        return {
            appendToForm: appendToForm,
            checkoutPayment: checkoutPayment,
            hideVoucherForm: hideVoucherForm,
            onSuccess: onSuccess,
            onFail: onFail,
            onReady: onReady,
            showVoucherForm: showVoucherForm,
        };
    }
);
