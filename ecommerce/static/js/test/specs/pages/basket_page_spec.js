define([
        'jquery',
        'underscore',
        'pages/basket_page',
        'utils/utils',
        'utils/analytics_utils',
        'models/tracking_model',
        'models/user_model',
        'views/analytics_view',
        'js-cookie',
        'moment'
    ],
    function ($,
              _,
              BasketPage,
              Utils,
              AnalyticsUtils,
              TrackingModel,
              UserModel,
              AnalyticsView,
              Cookies,
              moment
    ) {
        'use strict';

        describe('Basket Page', function () {
            var data,
                form;

            beforeEach(function () {
                $('<div class="spinner">' +
                    '<input class="quantity" id="id_form-0-quantity" min="1" max="10"' +
                    'name="form-0-quantity" type="number" value="1">' +
                    '<div class="input-group-btn-vertical">' +
                    '<button class="btn btn-primary" type="button">' +
                    '<i class="fa fa-caret-up"></i></button>' +
                    '<button class="btn btn-primary" type="button">' +
                    '<i class="fa fa-caret-down"></i></button></div></div>' +
                    '<div id="voucher_form_container"><input id="id_code">' +
                    '<a id="voucher_form_cancel"></a></button></div>' +
                    '<div id="voucher_form_link"><a href=""></a></div>' +
                    '<button type="submit" class="apply_voucher"' +
                    'data-track-type="click" data-track-event="edx.bi.ecommerce.basket.voucher_applied"' +
                    'data-voucher-code="ABCDEF"></button></div>' +
                    '<div class="payment-buttons">' +
                    '<button data-track-type="click"' +
                    'data-track-event="edx.bi.ecommerce.basket.payment_selected"' +
                    'data-track-category="cybersource"' +
                    'data-processor-name="cybersource"' +
                    'class="btn btn-success payment-button"' +
                    'value="cybersource"' +
                    'id="cybersource"></button></div>' +
                    '<div><input type="number" id="card-number-input" name="card_number">' +
                    '<img class="card-type-icon" src>' +
                    '<input type="hidden" name="card_type" value>' +
                    '<p class="validation-error"></div>'
                ).appendTo('body');


                $('<script type="text/javascript">var initModelData = {};</script>').appendTo('body');

                data = {
                    basket_id: 1,
                    payment_processor: 'paypal',
                    payment_page_url: 'http://www.dummy-url.com/',
                    payment_form_data: {
                        type: 'Dummy Type',
                        model: '500',
                        color: 'white'
                    }
                };

                form = $('<form>', {
                    action: data.payment_page_url,
                    method: 'POST',
                    'accept-method': 'UTF-8'
                });
            });

            afterEach(function () {
                $('body').empty();
            });

            describe('showVoucherForm', function () {
                it('should show voucher form', function () {
                    BasketPage.showVoucherForm();
                    expect($('#voucher_form_container').is(':visible')).toBeTruthy();
                    expect($('#voucher_form_link').is(':visible')).toBeFalsy();
                    expect($('#id_code').is(':focus')).toBeTruthy();
                });
            });

            describe('hideVoucherForm', function () {
                it('should hide voucher form', function () {
                    BasketPage.showVoucherForm();
                    BasketPage.hideVoucherForm();
                    expect($('#voucher_form_container').is(':visible')).toBeFalsy();
                    expect($('#voucher_form_link').is(':visible')).toBeTruthy();
                });
            });

            describe('onReady', function () {
                it('should toggle voucher form on click', function () {
                    BasketPage.onReady();

                    $('#voucher_form_link a').trigger('click');
                    expect($('#voucher_form_container').is(':visible')).toBeTruthy();
                    expect($('#voucher_form_link').is(':visible')).toBeFalsy();
                    expect($('#id_code').is(':focus')).toBeTruthy();

                    $('#voucher_form_cancel').trigger('click');
                    expect($('#voucher_form_container').is(':visible')).toBeFalsy();
                    expect($('#voucher_form_link').is(':visible')).toBeTruthy();
                });

                it('should make the states input field dropdown for US and CA', function() {
                    $(
                        '<fieldset>' +
                        '<div class="form-item"><div><select name="country">' +
                        '<option value=""><Choose country></option>' +
                        '<option value="US">United States</option>' +
                        '<option value="CA">Canada</option>' +
                        '<option value="HR">Croatia</option>' +
                        '</select></div><p class="help-block"></p></div>' +
                        '<div class="form-item"><div id="div_id_state"><div class="controls">' +
                        '<input name="state"></div></div>' +
                        '</fieldset>'
                    ).appendTo('body');
                    BasketPage.onReady();

                    $('select[name=country]').val('US').trigger('change');
                    expect($('#id_state').prop('tagName')).toEqual('SELECT');

                    $('select[name=country]').val('HR').trigger('change');
                    expect($('#id_state').prop('tagName')).toEqual('INPUT');

                    $('select[name=country]').val('CA').trigger('change');
                    expect($('#id_state').prop('tagName')).toEqual('SELECT');
                });

                it('should disable payment button before making ajax call', function () {
                    spyOn(Utils, 'disableElementWhileRunning').and.callThrough();
                    BasketPage.onReady();
                    $('button.payment-button').trigger('click');
                    expect(Utils.disableElementWhileRunning).toHaveBeenCalled();
                    expect($('button#cybersource').hasClass('is-disabled')).toBeTruthy();
                });

                it('should increment basket quantity on clicking up arrow', function () {
                    BasketPage.onReady();

                    $('input.quantity').first().val(5);
                    $('.spinner button.btn:first-of-type').trigger('click');

                    expect($('input.quantity').first().val()).toEqual('6');
                });

                it('should not increment quantity once reached to max value', function () {
                    BasketPage.onReady();

                    $('input.quantity').first().val(10);
                    $('.spinner button.btn:first-of-type').trigger('click');
                    expect($('input.quantity').first().val()).toEqual('10');
                });

                it('should decrement basket quantity on clicking down arrow', function () {
                    BasketPage.onReady();

                    $('input.quantity').first().val(5);
                    $('.spinner button.btn:last-of-type').trigger('click');

                    expect($('input.quantity').first().val()).toEqual('4');
                });

                it('should not decrement quantity once reached to min value', function () {
                    BasketPage.onReady();

                    $('input.quantity').first().val(1);
                    $('.spinner button.btn:last-of-type').trigger('click');
                    expect($('input.quantity').first().val()).toEqual('1');
                });

                it('should recognize the credit card', function() {
                    var validCardList = [
                        {'number': '378282246310005', 'name': 'amex', 'type': '003'},
                        {'number': '30569309025904', 'name': 'diners', 'type': '005'},
                        {'number': '6011111111111117', 'name': 'discover', 'type': '004'},
                        {'number': '3530111333300000', 'name': 'jcb', 'type': '007'},
                        {'number': '5105105105105100', 'name': 'mastercard', 'type': '002'},
                        {'number': '4111111111111111', 'name': 'visa', 'type': '001'},
                        {'number': '6759649826438453', 'name': 'maestro', 'type': '042'}
                    ];
                    BasketPage.onReady();

                    $('#card-number-input').trigger('input');
                    expect($('.card-type-icon').attr('src')).toEqual('');
                    expect($('input[name=card_type]').val()).toEqual('');

                    $('#card-number-input').val('123123123123123').trigger('input');
                    expect($('.card-type-icon').attr('src')).toEqual('');
                    expect($('input[name=card_type]').val()).toEqual('');

                    _.each(validCardList, function(card) {
                        $('#card-number-input').val(card.number).trigger('input');
                        expect($('.card-type-icon').attr('src')).toEqual(
                            '/static/images/credit_cards/' + card.name + '.png'
                        );
                        expect($('input[name=card_type]').val()).toEqual(card.type);
                    });
                });
            });

            describe('clientSideCheckoutValidation', function() {
            var cc_expiry_months = {
                    JAN: '01',
                    FEB: '02',
                    MAR: '03',
                    APR: '04',
                    MAY: '05',
                    JUN: '06',
                    JUL: '07',
                    AUG: '08',
                    SEP: '09',
                    OCT: '10',
                    NOV: '11',
                    DEC: '12'
                };


                beforeEach(function() {
                    $(
                        '<fieldset>' +
                        '<div class="form-item"><div><input name="first_name"></div>' +
                        '<p class="help-block"></p></div>' +
                        '<div class="form-item"><div><input name="last_name"></div>' +
                        '<p class="help-block"></p></div>' +
                        '<div class="form-item"><div><input name="address_line1"></div>' +
                        '<p class="help-block"></p></div>' +
                        '<div class="form-item"><div><input name="city"></div>' +
                        '<p class="help-block"></p></div>' +
                        '<div class="form-item"><div><select name="country">' +
                        '<option value=""><Choose country></option>' +
                        '<option value="US">United States</option>' +
                        '</select></div><p class="help-block"></p></div>' +
                        '</fieldset>' +
                        '<div><input name="card_number">' +
                        '<p class="help-block"></p></div>' +
                        '<div><input name="card_cvn">' +
                        '<p class="help-block"></p></div>' +
                        '<div><select name="card_expiry_month">' +
                        '<option value="99">99</option>' +
                        '</select>' +
                        '<p class="help-block"></p></div>' +
                        '<div><select name="card_expiry_year">' +
                        '<option value="2015">2015</option>' +
                        '</select>' +
                        '<p class="help-block"></p></div>' +
                        '<button id="payment-button">Pay</button>'
                    ).appendTo('body');

                    $('select[name=card_expiry_month]').append(
                        _.reduce(_.toArray(cc_expiry_months), function(memo, value){
                            return memo + '<option value="' + value + '">' + value + '</option>';
                        }, '')
                    );

                    $('input[name=first_name]').val('Joey');
                    $('input[name=last_name]').val('Tribbiani');
                    $('input[name=address_line1]').val('Central Perk');
                    $('input[name=city]').val('New York City');
                    $('select[name=country]').val('US');

                    BasketPage.onReady();
                });

                describe('cardHolderInformationValidation', function() {
                    it('should validate first name', function() {
                        $('input[name=first_name]').val('');
                        $('#payment-button').click();

                        expect(
                            $('input[name=first_name]').parentsUntil(
                                'form-item'
                            ).find('~.help-block span').text()
                        ).toEqual('This field is required');
                    });

                    it('should validate last name', function() {
                        $('input[name=last_name]').val('');
                        $('#payment-button').click();

                        expect(
                            $('input[name=last_name]').parentsUntil(
                                'form-item'
                            ).find('~.help-block span').text()
                        ).toEqual('This field is required');
                    });

                    it('should validate address', function() {
                        $('input[name=address_line1]').val('');
                        $('#payment-button').click();

                        expect(
                            $('input[name=address_line1]').parentsUntil(
                                'form-item'
                            ).find('~.help-block span').text()
                        ).toEqual('This field is required');
                    });

                    it('should validate city', function() {
                        $('input[name=city]').val('');
                        $('#payment-button').click();

                        expect(
                            $('input[name=city]').parentsUntil(
                                'form-item'
                            ).find('~.help-block span').text()
                        ).toEqual('This field is required');
                    });

                    it('should validate country', function() {
                        $('select[name=country]').val('');
                        $('#payment-button').click();

                        expect(
                            $('select[name=country]').parentsUntil(
                                'form-item'
                            ).find('~.help-block span').text()
                        ).toEqual('This field is required');
                    });

                });

                describe('cardInfoValidation', function() {
                    var validCardNumber = '378282246310005',  // AMEX (CVN length 4)
                        validCvn = '1234',
                        enRouteCardNumber = '201401173701274', // Unsupported type (Dec, 2016)
                        today = moment(),
                        cardExpirationMonth = 'FEB',  // Card Expires in February
                        thisMonth = moment().month('MAR').month(); // Let's say this month is March

                    beforeEach (function () {
                        $('select[name=card_expiry_year]').append('<option value="' +
                            today.year() + '">' + today.year() + '</option>'
                        );
                        // Freeze month to March.
                        // We are using moment here to get number of month instead of
                        // hard coding it, so that it conforms to js date time style.
                        spyOn(Date.prototype, 'getMonth').and.returnValue(thisMonth);
                    });

                    it('should validate card number', function() {
                        $('input[name=card_number]').val('123invalid456');
                        $('#payment-button').click();
                        expect($('input[name=card_number] ~ .help-block span').text()).toEqual('Invalid card number');

                        $('input[name=card_number]').val(validCardNumber);
                        $('#payment-button').click();
                        expect($('input[name=card_number] ~ .help-block').has('span').length).toEqual(0);
                    });

                    it('should validate card type', function() {
                        $('input[name=card_number]').val(enRouteCardNumber);
                        $('#payment-button').click();
                        expect($('input[name=card_number]~.help-block span').text()).toEqual('Unsupported card type');

                        $('input[name=card_number]').val(validCardNumber);
                        $('#payment-button').click();
                        expect($('input[name=card_number] ~ .help-block').has('span').length).toEqual(0);
                    });

                    it('should validate CVN number', function() {
                        $('input[name=card_number]').val(validCardNumber);
                        $('input[name=card_cvn]').val('123');
                        $('#payment-button').click();
                        expect($('input[name=card_cvn] ~ .help-block span').text()).toEqual('Invalid CVN');

                        $('input[name=card_cvn]').val('123b');
                        $('#payment-button').click();
                        expect($('input[name=card_cvn] ~ .help-block span').text()).toEqual('Invalid CVN');

                        $('input[name=card_cvn]').val(validCvn);
                        $('#payment-button').click();
                        expect($('input[name=card_number] ~ .help-block').has('span').length).toEqual(0);
                    });

                    it('should validate expiry month', function() {
                        $('input[name=card_number]').val(validCardNumber);
                        $('input[name=card_cvn]').val(validCvn);
                        $('select[name=card_expiry_month]').val('99');
                        $('#payment-button').click();
                        expect($('select[name=card_expiry_month]~.help-block span').text()).toEqual('Invalid month');

                        $('select[name=card_expiry_month]').val('12');
                        $('#payment-button').click();
                        expect($('select[name=card_expiry_month] ~ .help-block').has('span').length).toEqual(0);
                    });

                    it('should validate expiry year', function() {
                        $('input[name=card_number]').val(validCardNumber);
                        $('input[name=card_cvn]').val(validCvn);
                        $('select[name=card_expiry_month]').val('12');
                        $('select[name=card_expiry_year]').val('2015');
                        $('#payment-button').click();
                        expect($('select[name=card_expiry_year] ~ .help-block span').text()).toEqual('Invalid year');

                        $('select[name=card_expiry_year]').val(today.year());
                        $('#payment-button').click();
                        expect($('select[name=card_expiry_year] ~ .help-block').has('span').length).toEqual(0);
                    });

                    it('should validate card expiration', function() {
                        $('input[name=card_number]').val(validCardNumber);
                        $('input[name=card_cvn]').val(validCvn);
                        $('select[name=card_expiry_month]').val(cc_expiry_months[cardExpirationMonth]);
                        $('select[name=card_expiry_year]').val(today.year());
                        $('#payment-button').click();
                        expect($('select[name=card_expiry_month] ~ .help-block span').text()).toEqual('Card expired');

                        $('select[name=card_expiry_month]').val('12');
                        $('select[name=card_expiry_year]').val(today.year());
                        $('#payment-button').click();
                        expect($('select[name=card_expiry_month] ~ .help-block').has('span').length).toEqual(0);
                    });
                });
            });

            describe('appendToForm', function () {
                it('should append input data to form', function () {
                    _.each(data.payment_form_data, function(value, key) {
                        BasketPage.appendToForm(value, key, form);
                    });
                    expect(form.children().length).toEqual(3);
                });
            });

            describe('onFail', function () {
                it('should report error to message div element', function () {
                    $('<div id="messages"></div>').appendTo('body');
                    var error_messages_div = $('#messages');
                    BasketPage.onFail();
                    expect(error_messages_div.text()).toEqual(
                        'Problem occurred during checkout. Please contact support'
                    );
                });
            });

            describe('checkoutPayment', function () {
                it('should POST to the checkout endpoint', function () {
                    var args,
                        cookie = 'checkout-payment-test';

                    spyOn($, 'ajax');
                    Cookies.set('ecommerce_csrftoken', cookie);

                    BasketPage.checkoutPayment(data);

                    // $.ajax should have been called
                    expect($.ajax).toHaveBeenCalled();

                    // Ensure the data was POSTed to the correct endpoint
                    args = $.ajax.calls.argsFor(0)[0];
                    expect(args.method).toEqual('POST');
                    expect(args.url).toEqual('/api/v2/checkout/');
                    expect(args.contentType).toEqual('application/json; charset=utf-8');
                    expect(args.headers).toEqual({'X-CSRFToken': cookie});
                    expect(JSON.parse(args.data)).toEqual(data);
                });
            });

            describe('Analytics', function() {
                beforeEach(function () {
                    spyOn(TrackingModel.prototype, 'isTracking').and.callFake(function() {
                        return true;
                    });
                    spyOn(AnalyticsView.prototype, 'track');
                    AnalyticsUtils.analyticsSetUp();
                    BasketPage.onReady();
                    spyOn(window.analytics, 'page');
                });

                it('should trigger voucher applied analytics event', function() {
                    $('button.apply_voucher').trigger('click');
                    expect(AnalyticsView.prototype.track).toHaveBeenCalledWith(
                        'edx.bi.ecommerce.basket.voucher_applied',
                        { type: 'click' }
                    );
                });

                it('should trigger checkout analytics event', function() {
                    $('button.payment-button').trigger('click');
                    expect(AnalyticsView.prototype.track).toHaveBeenCalledWith(
                        'edx.bi.ecommerce.basket.payment_selected',
                        { category: 'cybersource', type: 'click' }
                    );
                });

                it('should trigger page load analytics event', function() {
                    AnalyticsUtils.analyticsSetUp();
                    expect(window.analytics.page).toHaveBeenCalled();
                });
            });
        });
    }
);
