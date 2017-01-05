/**
 * Basket page scripts.
 **/

define([
        'jquery',
        'underscore',
        'underscore.string',
        'utils/utils',
        'utils/credit_card',
        'js-cookie'
    ],
    function ($,
              _,
              _s,
              Utils,
              CreditCardUtils,
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
        appendCardValidationErrorMsg = function(event, field, msg) {
            field.find('~.help-block').append('<span>' + msg + '</span>');
            field.focus();
            event.preventDefault();
        },

        appendCardHolderValidationErrorMsg = function(field, msg) {
            field.parentsUntil('form-item').find('~.help-block').append(
                '<span>' + msg + '</span>'
            );
        },

        cardHolderInfoValidation = function (event) {
            var requiredFields = [
                'input[name=first_name]',
                'input[name=last_name]',
                'input[name=address_line1]',
                'input[name=city]',
                'select[name=country]'
            ];

            _.each(requiredFields, function(field) {
                if ($(field).val() === '') {
                    event.preventDefault();
                    appendCardHolderValidationErrorMsg($(field), 'This field is required');
                }
            });

            // Focus the first element that has an error message.
            $('.help-block > span').first().parentsUntil('fieldset').last().find('input').focus();
        },

        cardInfoValidation = function (event) {
            var cardType,
                // We are adding 1 here because month in js style date-time starts with 0
                // i.e. 0 for JAN, 1 for FEB etc. However, credit card expiry months start with 1
                // i.e 1 for JAN, 2 for FEB etc.
                currentMonth = new Date().getMonth() + 1,
                currentYear = new Date().getFullYear(),
                cardNumber = $('input[name=card_number]').val(),
                cvnNumber = $('input[name=card_cvn]').val(),
                cardExpiryMonth = $('select[name=card_expiry_month]').val(),
                cardExpiryYear = $('select[name=card_expiry_year]').val(),
                cardNumberField = $('input[name=card_number]'),
                cvnNumberField = $('input[name=card_cvn]'),
                cardExpiryMonthField = $('select[name=card_expiry_month]'),
                cardExpiryYearField = $('select[name=card_expiry_year]');

            cardType = CreditCardUtils.getCreditCardType(cardNumber);

            if (!CreditCardUtils.isValidCardNumber(cardNumber)) {
                appendCardValidationErrorMsg(event, cardNumberField, 'Invalid card number');
            } else if (typeof cardType === 'undefined') {
                appendCardValidationErrorMsg(event, cardNumberField, 'Unsupported card type');
            } else if (cvnNumber.length !== cardType.cvnLength || !Number.isInteger(Number(cvnNumber))) {
                appendCardValidationErrorMsg(event, cvnNumberField, 'Invalid CVN');
            }

            if (!Number.isInteger(Number(cardExpiryMonth)) ||
                Number(cardExpiryMonth) > 12 || Number(cardExpiryMonth) < 1) {
                appendCardValidationErrorMsg(event, cardExpiryMonthField, 'Invalid month');
            } else if (!Number.isInteger(Number(cardExpiryYear)) || Number(cardExpiryYear) < currentYear) {
                appendCardValidationErrorMsg(event, cardExpiryYearField, 'Invalid year');
            } else if (Number(cardExpiryMonth) < currentMonth && Number(cardExpiryYear) === currentYear) {
                appendCardValidationErrorMsg(event, cardExpiryMonthField, 'Card expired');
            }
        },

        detectCreditCard = function() {
            var cardNumber = $('#card-number-input').val().replace(/\s+/g, ''),
                card,
                iconPath = '/static/images/credit_cards/';

            if (cardNumber.length > 12) {
                card = CreditCardUtils.getCreditCardType(cardNumber);

                if (typeof card !== 'undefined') {
                    $('.card-type-icon').attr(
                        'src',
                        iconPath + card.name + '.png'
                    ).removeClass('hidden');
                    $('input[name=card_type]').val(card.type);
                } else {
                    $('.card-type-icon').attr('src', '').addClass('hidden');
                    $('input[name=card_type]').val('');
                }
            } else {
                $('.card-type-icon').attr('src', '').addClass('hidden');
            }
        },

        onReady = function() {
            var $paymentButtons = $('.payment-buttons'),
                basketId = $paymentButtons.data('basket-id');

            $('#voucher_form_link').on('click', function(event) {
                event.preventDefault();
                showVoucherForm();
            });

            $('#voucher_form_cancel').on('click', function(event) {
                event.preventDefault();
                hideVoucherForm();
            });

            $('select[name=country]').on('change', function() {
                var country = $('select[name=country]').val(),
                    inputDiv = $('#div_id_state .controls'),
                    states = {
                        'US': {
                            'Alabama': 'AL',
                            'Alaska': 'AK',
                            'American': 'AS',
                            'Arizona': 'AZ',
                            'Arkansas': 'AR',
                            'California': 'CA',
                            'Colorado': 'CO',
                            'Connecticut': 'CT',
                            'Delaware': 'DE',
                            'Dist. of Columbia': 'DC',
                            'Florida': 'FL',
                            'Georgia': 'GA',
                            'Guam': 'GU',
                            'Hawaii': 'HI',
                            'Idaho': 'ID',
                            'Illinois': 'IL',
                            'Indiana': 'IN',
                            'Iowa': 'IA',
                            'Kansas': 'KS',
                            'Kentucky': 'KY',
                            'Louisiana': 'LA',
                            'Maine': 'ME',
                            'Maryland': 'MD',
                            'Marshall Islands': 'MH',
                            'Massachusetts': 'MA',
                            'Michigan': 'MI',
                            'Micronesia': 'FM',
                            'Minnesota': 'MN',
                            'Mississippi': 'MS',
                            'Missouri': 'MO',
                            'Montana': 'MT',
                            'Nebraska': 'NE',
                            'Nevada': 'NV',
                            'New Hampshire': 'NH',
                            'New Jersey': 'NJ',
                            'New Mexico': 'NM',
                            'New York': 'NY',
                            'North Carolina': 'NC',
                            'North Dakota': 'ND',
                            'Northern Marianas': 'MP',
                            'Ohio': 'OH',
                            'Oklahoma': 'OK',
                            'Oregon': 'OR',
                            'Palau': 'PW',
                            'Pennsylvania': 'PA',
                            'Puerto Rico': 'PR',
                            'Rhode Island': 'RI',
                            'South Carolina': 'SC',
                            'South Dakota': 'SD',
                            'Tennessee': 'TN',
                            'Texas': 'TX',
                            'Utah': 'UT',
                            'Vermont': 'VT',
                            'Virginia': 'VA',
                            'Virgin Islands': 'VI',
                            'Washington': 'WA',
                            'West Virginia': 'WV',
                            'Wisconsin': 'WI',
                            'Wyoming': 'WY'
                        },
                        'CA': {
                            'Alberta': 'AB',
                            'British Columbia': 'BC',
                            'Manitoba': 'MB',
                            'New Brunswick': 'NB',
                            'Newfoundland and Labrador': 'NL',
                            'Northwest Territories': 'NT',
                            'Nova Scotia': 'NS',
                            'Nunavut': 'NU',
                            'Ontario': 'ON',
                            'Prince Edward Island': 'PE',
                            'Quebec': 'QC',
                            'Saskatchewan': 'SK',
                            'Yukon': 'YT'
                        }
                    };

                if (country === 'US' || country === 'CA') {
                    $(inputDiv).empty();
                    $(inputDiv).append(
                        '<select name="state" class="select form-control" id="id_state"' +
                        'aria-required="true" required></select>'
                    );
                    _.each(states[country], function(value, key) {
                        $('#id_state').append($('<option>', {value: value, text: key}));
                    });
                } else {
                    $(inputDiv).empty();
                    // In order to change the maxlength attribute, the same needs to be changed in the Django form.
                    $(inputDiv).append(
                        '<input class="textinput textInput form-control" id="id_state"' +
                        'maxlength="60" name="state" type="text">'
                    );
                }
            });

            $('#card-number-input').on('input', function() {
                detectCreditCard();
            });

            $('#payment-button').click(function(e) {
                _.each($('.help-block'), function(errorMsg) {
                    $(errorMsg).empty();  // Clear existing validation error messages.
                });
                if ($('#card-number-input').val()) {
                    detectCreditCard();
                }
                cardInfoValidation(e);
                cardHolderInfoValidation(e);
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
            appendCardHolderValidationErrorMsg: appendCardHolderValidationErrorMsg,
            appendToForm: appendToForm,
            cardInfoValidation: cardInfoValidation,
            checkoutPayment: checkoutPayment,
            hideVoucherForm: hideVoucherForm,
            onFail: onFail,
            onReady: onReady,
            onSuccess: onSuccess,
            showVoucherForm: showVoucherForm,
        };
    }
);
