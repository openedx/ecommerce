define([
        'jquery',
        'underscore',
        'pages/basket_page',
        'utils/utils',
    ],
    function ($,
              _,
              BasketPage,
              Utils) {
        'use strict';

        describe('Basket Page', function () {
            var data,
                form;

            beforeEach(function () {
                $('<div id="voucher_form_container"><input id="id_code">' +
                    '<a id="voucher_form_cancel"></a></button></div>' +
                    '<div id="voucher_form_link"><a href=""></a></div>' +
                    '<div class="payment-buttons"><button class="">' +
                    '</div>'
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

            describe('onReady', function () {
                it('should disable payment button before making ajax call', function () {
                    $('<div class="payment-buttons"><button class="payment-button">Pay</button></div>')
                        .appendTo('body');
                    spyOn(Utils, 'disableElementWhileRunning');
                    BasketPage.onReady();
                    $('button.payment-button').trigger('click');
                    expect(Utils.disableElementWhileRunning).toHaveBeenCalled();
                });
            });

            describe('checkoutPayment', function () {
                it('should POST to the checkout endpoint', function () {
                    var args,
                        cookie = 'checkout-payment-test';

                    spyOn($, 'ajax');
                    $.cookie('ecommerce_csrftoken', cookie);

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
        });
    }
);
