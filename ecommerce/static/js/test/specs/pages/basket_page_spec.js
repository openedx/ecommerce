define([
        'jquery',
        'underscore',
        'pages/basket_page',
        'utils/utils',
        'utils/analytics_utils',
        'models/tracking_model',
        'models/user_model',
        'views/analytics_view',
        'js-cookie'
    ],
    function ($,
              _,
              BasketPage,
              Utils,
              AnalyticsUtils,
              TrackingModel,
              UserModel,
              AnalyticsView,
              Cookies
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
                    'id="cybersource"></button></div>'
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
