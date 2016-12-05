/**
 * Basket page scripts.
 **/

define([
        'jquery',
        'underscore',
        'underscore.string',
        'utils/utils',
        'js-cookie'
    ],
    function ($,
              _,
              _s,
              Utils,
              Cookies
    ) {
        'use strict';

        var appendToForm = function (value, key, form) {
            $('<input>').attr({
                type: 'text',
                name: key,
                value: value
            }).appendTo(form);
        },
        getCreditCardType = function(cardNumber) {
            var matchers = {
                    amex: [/^3[47]\d{13}$/, '003'],
                    diners: [/^3(?:0[0-59]|[689]\d)\d{11}$/, '005'],
                    discover: [
                        /^(6011\d{2}|65\d{4}|64[4-9]\d{3}|62212[6-9]|6221[3-9]\d|622[2-8]\d{2}|6229[01]\d|62292[0-5])\d{10,13}$/,  // jshint ignore:line
                        '004'
                    ],
                    jcb: [/^(?:2131|1800|35\d{3})\d{11}$/, '007'],
                    maestro: [/^(5[06789]|6\d)[0-9]{10,17}$/, '042'],
                    mastercard: [/^(5[1-5]\d{2}|222[1-9]|22[3-9]\d|2[3-6]\d{2}|27[01]\d|2720)\d{12}$/, '002'],
                    visa: [/^(4\d{12}?(\d{3})?)$/, '001']
                };

            for (var key in matchers) {
                if (matchers[key][0].test(cardNumber)) {
                    return {
                        'name': key,
                        'type': matchers[key][1]
                    };
                }
            }
        },
        checkoutPayment = function(data) {
            $.ajax({
                url: '/api/v2/checkout/',
                method: 'POST',
                contentType: 'application/json; charset=utf-8',
                dataType: 'json',
                headers: {
                    'X-CSRFToken': Cookies.get('ecommerce_csrftoken')
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
                basketId = $paymentButtons.data('basket-id'),
                iconPath = '/static/images/credit_cards/';

            $('#voucher_form_link').on('click', function(event) {
                event.preventDefault();
                showVoucherForm();
            });

            $('#voucher_form_cancel').on('click', function(event) {
                event.preventDefault();
                hideVoucherForm();
            });

            $('#id_card_number').on('input', function() {
                var cardNumber = $('#id_card_number').val().replace(/\s+/g, ''),
                    card = getCreditCardType(cardNumber);

                if (cardNumber.length > 13 && cardNumber.length < 19){
                    var color = (Utils.isValidCardNumber(cardNumber)) ? 'black' : 'red';
                    $('#id_card_number').css('color', color);
                }

                if (typeof card !== 'undefined') {
                    $('.card-type-icon').attr(
                        'src',
                        iconPath + card.name + '.png'
                    );
                    $('input[name=card_type]').val(card.type);
                } else {
                    $('.card-type-icon').attr('src', '');
                    $('input[name=card_type]').val('');
                }
            });

            $paymentButtons.find('.payment-button').click(function (e) {
                var $btn = $(e.target),
                    deferred = new $.Deferred(),
                    promise = deferred.promise(),
                    paymentProcessor = $btn.data('processor-name'),
                    data = {
                        basket_id: basketId,
                        payment_processor: paymentProcessor
                    };

                Utils.disableElementWhileRunning($btn, function() { return promise; });
                checkoutPayment(data);
            });

            // Increment the quantity field until max
            $('.spinner .btn:first-of-type').on('click', function() {
                var btn = $(this);
                var input = btn.closest('.spinner').find('input');
                // Stop if max attribute is defined and value is reached to given max value
                if (input.attr('max') === undefined || parseInt(input.val()) < parseInt(input.attr('max'))) {
                    input.val(parseInt(input.val()) + 1);
                } else {
                    btn.next('disabled', true);
                }
            });

            // Decrement the quantity field until min
            $('.spinner .btn:last-of-type').on('click', function() {
                var btn = $(this);
                var input = btn.closest('.spinner').find('input');
                // Stop if min attribute is defined and value is reached to given min value
                if (input.attr('min') === undefined || parseInt(input.val()) > parseInt(input.attr('min'))) {
                    input.val(parseInt(input.val()) - 1);
                } else {
                    btn.prev('disabled', true);
                }
            });
        },
        showVoucherForm = function() {
            $('#voucher_form_container').show();
            $('#voucher_form_link').hide();
            $('#id_code').focus();
        };

        return {
            appendToForm: appendToForm,
            getCreditCardType: getCreditCardType,
            checkoutPayment: checkoutPayment,
            hideVoucherForm: hideVoucherForm,
            onSuccess: onSuccess,
            onFail: onFail,
            onReady: onReady,
            showVoucherForm: showVoucherForm,
        };
    }
);
