define([
    'jquery',
    'underscore',
    'underscore.string',
    'pages/basket_page',
    'utils/utils',
    'utils/analytics_utils',
    'models/tracking_model',
    'models/user_model',
    'js-cookie',
    'moment'
],
    function($,
              _,
              _s,
              BasketPage,
              Utils,
              AnalyticsUtils,
              TrackingModel,
              UserModel,
              Cookies,
              moment) {
        'use strict';

        describe('Basket Page', function() {
            var data;

            beforeEach(function() {
                jasmine.getFixtures().fixturesPath = '/base/ecommerce/static/js/test/fixtures';
            });

            beforeEach(function() {
                loadFixtures('basket.html');

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

                /* eslint-disable */
                window.analytics = window.analytics || []; if (!analytics.initialize) if (analytics.invoked)window.console && console.error && console.error('Segment snippet included twice.'); else { analytics.invoked = !0; analytics.methods = ['trackSubmit', 'trackClick', 'trackLink', 'trackForm', 'pageview', 'identify', 'group', 'track', 'ready', 'alias', 'page', 'once', 'off', 'on']; analytics.factory = function(t) { return function() { var e = Array.prototype.slice.call(arguments); e.unshift(t); analytics.push(e); return analytics; }; }; for (var t = 0; t < analytics.methods.length; t++) { var e = analytics.methods[t]; analytics[e] = analytics.factory(e); }analytics.load = function(t) { var e = document.createElement('script'); e.type = 'text/javascript'; e.async = !0; e.src = (document.location.protocol === 'https:' ? 'https://' : 'http://') + 'cdn.segment.com/analytics.js/v1/' + t + '/analytics.min.js'; var n = document.getElementsByTagName('script')[0]; n.parentNode.insertBefore(e, n); }; analytics.SNIPPET_VERSION = '3.0.1'; }
                /* eslint-enable */
            });

            afterEach(function() {
                $('body').empty();
            });

            describe('showVoucherForm', function() {
                it('should show voucher form', function() {
                    BasketPage.showVoucherForm();
                    expect($('#voucher_form_container').is(':visible')).toBeTruthy();
                    expect($('#voucher_form_link').is(':visible')).toBeFalsy();
                    expect($('#id_code').is(':focus')).toBeTruthy();
                });
            });

            describe('hideVoucherForm', function() {
                it('should hide voucher form', function() {
                    BasketPage.showVoucherForm();
                    BasketPage.hideVoucherForm();
                    expect($('#voucher_form_container').is(':visible')).toBeFalsy();
                    expect($('#voucher_form_link').is(':visible')).toBeTruthy();
                });
            });

            describe('onReady', function() {
                it('should toggle voucher form on click', function() {
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
                        '<div class="form-item"><div id="div_id_state"><label>State/Province</label>' +
                        '<div class="controls"><input name="state"></div></div></div>' +
                        '</fieldset>'
                    ).appendTo('body');
                    BasketPage.onReady();

                    $('select[name=country]').val('US').trigger('change');
                    expect($('#id_state').prop('tagName')).toEqual('SELECT');

                    $('select[name=country]').val('HR').trigger('change');
                    expect($('#id_state').prop('tagName')).toEqual('INPUT');

                    $('select[name=country]').val('CA').trigger('change');
                    expect($('#id_state').prop('tagName')).toEqual('SELECT');
                    expect($('#div_id_state').find('label').text()).toEqual('State/Province (required)');
                });

                it('should disable payment button before making ajax call', function() {
                    spyOn(Utils, 'disableElementWhileRunning').and.callThrough();
                    BasketPage.onReady();
                    $('button.payment-button').trigger('click');
                    expect(Utils.disableElementWhileRunning).toHaveBeenCalled();
                    expect($('button#cybersource').hasClass('is-disabled')).toBeTruthy();
                });

                it('should increment basket quantity on clicking up arrow', function() {
                    BasketPage.onReady();

                    $('input.quantity').first().val(5);
                    $('.spinner button.btn:first-of-type').trigger('click');

                    expect($('input.quantity').first().val()).toEqual('6');
                });

                it('should not increment quantity once reached to max value', function() {
                    BasketPage.onReady();

                    $('input.quantity').first().val(10);
                    $('.spinner button.btn:first-of-type').trigger('click');
                    expect($('input.quantity').first().val()).toEqual('10');
                });

                it('should decrement basket quantity on clicking down arrow', function() {
                    BasketPage.onReady();

                    $('input.quantity').first().val(5);
                    $('.spinner button.btn:last-of-type').trigger('click');

                    expect($('input.quantity').first().val()).toEqual('4');
                });

                it('should not decrement quantity once reached to min value', function() {
                    var $quantity = $('input.quantity');
                    BasketPage.onReady();

                    $quantity.first().val(1);
                    $('.spinner button.btn:last-of-type').trigger('click');
                    expect($quantity.first().val()).toEqual('1');
                });

                it('should show error message when quantity is greater than 100', function() {
                    BasketPage.onReady();

                    $('input.quantity').first().val(101);
                    $('#quantity-update').trigger('click');
                    expect($('div#error-msg').text()).toEqual('Quantity must be less than or equal to 100.');
                });

                it('should show error message when quantity is less than 1', function() {
                    BasketPage.onReady();

                    $('input.quantity').first().val(0);
                    $('#quantity-update').trigger('click');
                    expect($('div#error-msg').text()).toEqual('Quantity must be greater than or equal to 1.');
                });

                it('should show error message when quantity is not given', function() {
                    BasketPage.onReady();

                    $('input.quantity').first().val('');
                    $('#quantity-update').trigger('click');
                    expect($('div#error-msg').text()).toEqual('Please enter a quantity from 1 to 100.');
                });

                it('should recognize the credit card', function() {
                    var validCardList = [
                            {number: '378282246310005', name: 'amex'},
                            {number: '6011111111111117', name: 'discover'},
                            {number: '5105105105105100', name: 'mastercard'},
                            {number: '4111111111111111', name: 'visa'}
                        ],
                        cardNumberSelector = '#card-number',
                        $cardNumber = $(cardNumberSelector),
                        $cardTypeIcon = $('.card-type-icon');

                    spyOnEvent($cardNumber, 'cardType:detected');
                    BasketPage.onReady();

                    $cardNumber.trigger('input');
                    expect($cardTypeIcon.attr('src')).toEqual('');

                    $cardNumber.val('123123123123123').trigger('input');
                    expect($cardTypeIcon.attr('src')).toEqual('');

                    _.each(validCardList, function(card) {
                        var expectedImage = '/static/images/credit_cards/' + card.name + '.png';

                        $cardNumber.val(card.number).trigger('input');
                        expect($cardTypeIcon.attr('src')).toEqual(expectedImage);
                        expect('cardType:detected').toHaveBeenTriggeredOnAndWith(cardNumberSelector, {type: card.name});
                    });
                });

                it('should determine if credit card type is supported', function() {
                    var validCardTypes = ['amex', 'discover', 'mastercard', 'visa'],
                        invalidCardTypes = ['diners', 'jcb', 'maestro'];

                    _.each(validCardTypes, function(cardType) {
                        expect(BasketPage.isCardTypeSupported(cardType)).toBeTruthy();
                    });

                    _.each(invalidCardTypes, function(cardType) {
                        expect(BasketPage.isCardTypeSupported(cardType)).toBeFalsy();
                    });
                });

                it('should prevent default on click behavior of the CVN help button', function() {
                    var event = $.Event('click');
                    BasketPage.onReady();
                    spyOn(event, 'preventDefault');
                    $('#card-cvn-help').trigger(event);
                    expect(event.preventDefault).toHaveBeenCalled();
                });

                it('should close cvv help tooltip once the escape button is pressed', function() {
                    BasketPage.onReady();
                    $(document).trigger($.Event('keyup', {which: 27}));
                    expect($('#cvvtooltip').is(':visible')).toBeFalsy();
                });

                it('should toggle cvv help tooltip on help button click', function() {
                    var $cvvtooltip = $('#cvvtooltip'),
                        $helpbutton = $('#card-cvn-help');
                    BasketPage.onReady();

                    $helpbutton.click();
                    expect($cvvtooltip.is(':visible')).toBeTruthy();
                    expect($helpbutton.attr('aria-haspopup')).toEqual('false');
                    expect($helpbutton.attr('aria-expanded')).toEqual('true');

                    $helpbutton.click();
                    expect($cvvtooltip.is(':visible')).toBeFalsy();
                    expect($helpbutton.attr('aria-haspopup')).toEqual('true');
                    expect($helpbutton.attr('aria-expanded')).toEqual('false');
                });

                it('should toggle cvv help tooltip on mouse hover', function() {
                    var $cvvtooltip = $('#cvvtooltip'),
                        $helpbutton = $('#card-cvn-help');
                    BasketPage.onReady();

                    $helpbutton.trigger('mouseover');
                    expect($cvvtooltip.is(':visible')).toBeTruthy();
                    expect($helpbutton.attr('aria-haspopup')).toEqual('false');
                    expect($helpbutton.attr('aria-expanded')).toEqual('true');

                    $helpbutton.trigger('mouseout');
                    expect($cvvtooltip.is(':visible')).toBeFalsy();
                    expect($helpbutton.attr('aria-haspopup')).toEqual('true');
                    expect($helpbutton.attr('aria-expanded')).toEqual('false');
                });

                it('should toggle cvv help tooltip on focus for keyboard users', function() {
                    var $cvvtooltip = $('#cvvtooltip'),
                        $helpbutton = $('#card-cvn-help');
                    BasketPage.onReady();

                    $helpbutton.trigger('focus');
                    $(document).trigger($.Event('keyup', {which: 9}));
                    expect($cvvtooltip.is(':visible')).toBeTruthy();
                    expect($helpbutton.attr('aria-haspopup')).toEqual('false');
                    expect($helpbutton.attr('aria-expanded')).toEqual('true');

                    $helpbutton.trigger('blur');
                    expect($cvvtooltip.is(':visible')).toBeFalsy();
                    expect($helpbutton.attr('aria-haspopup')).toEqual('true');
                    expect($helpbutton.attr('aria-expanded')).toEqual('false');
                });

                describe('Credit card detection occurs on local currency exception', function() {
                    it('should call #detectCreditCard on #addPriceDisclaimer exception', function() {
                        var cardNumberSelector = '#card-number',
                            $cardNumber = $(cardNumberSelector),
                            cardValue = 4111111111111111;

                        spyOn(BasketPage, 'detectCreditCard');
                        spyOn(BasketPage, 'addPriceDisclaimer').and.throwError('test price disclaimer error');

                        BasketPage.onReady();
                        $cardNumber.val(cardValue).trigger('input');

                        expect(BasketPage.detectCreditCard).toHaveBeenCalled();
                    });
                    it('should call #detectCreditCard on #translateToLocalPrices exception', function() {
                        var cardNumberSelector = '#card-number',
                            $cardNumber = $(cardNumberSelector),
                            cardValue = 4111111111111111;

                        spyOn(BasketPage, 'detectCreditCard');
                        spyOn(BasketPage, 'translateToLocalPrices')
                            .and.throwError('test local price translation error');

                        BasketPage.onReady();
                        $cardNumber.val(cardValue).trigger('input');

                        expect(BasketPage.detectCreditCard).toHaveBeenCalled();
                    });
                });
            });

            describe('clientSideCheckoutValidation', function() {
                var ccExpiryMonths = {
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
                    loadFixtures('client-side-checkout-basket.html');

                    $('#card-expiry-month').append(
                        _.reduce(_.toArray(ccExpiryMonths), function(memo, value) {
                            return memo + '<option value="' + value + '">' + value + '</option>';
                        }, '')
                    );

                    $('input[name=first_name]').val('Joey');
                    $('input[name=last_name]').val('Tribbiani');
                    $('input[name=address_line1]').val('Central Perk');
                    $('input[name=city]').val('New York City');
                    $('select[name=country]').val('US');
                    $('select[name=state]').val('NY');

                    BasketPage.onReady();
                });

                describe('cardHolderInformationValidation', function() {
                    it('should validate required fields', function() {
                        var requiredFields = [
                            'input[name=first_name]',
                            'input[name=last_name]',
                            'input[name=address_line1]',
                            'input[name=city]',
                            'select[name=country]'
                        ];

                        _.each(requiredFields, function(field) {
                            $(field).val('');
                            $('#payment-button').click();

                            expect(
                                $(field).parentsUntil('form-item').find('~.help-block span').text()
                            ).toEqual('This field is required');
                            expect($('.payment-form').attr('data-has-error')).toEqual('true');
                        });
                    });

                    it('should validate state field', function() {
                        $('select[name=country]').val('US').trigger('change');
                        $('select[name=state]').val('');
                        $('#payment-button').click();
                        expect(
                            $('select[name=state]').parentsUntil(
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

                    beforeEach(function() {
                        $('#card-expiry-year').append('<option value="' +
                            today.year() + '">' + today.year() + '</option>'
                        );
                        // Freeze month to March.
                        // We are using moment here to get number of month instead of
                        // hard coding it, so that it conforms to js date time style.
                        spyOn(Date.prototype, 'getMonth').and.returnValue(thisMonth);

                        $('#card-number').val(validCardNumber);
                        $('#card-cvn').val(validCvn);
                        $('#card-expiry-month').val(12);
                        $('#card-expiry-year').val(today.year());
                    });

                    function expectFormSubmitted(fieldName) {
                        expect($(fieldName + '~ .help-block').has('span').length).toEqual(0);
                        expect($('.payment-form').attr('data-has-error')).toEqual('false');
                    }

                    it('should validate card number', function() {
                        $('#card-number').val('123invalid456');
                        $('#payment-button').click();
                        expect($('#card-number ~ .help-block span').text()).toEqual('Invalid card number');
                        expect($('.payment-form').attr('data-has-error')).toEqual('true');

                        $('#card-number').val(validCardNumber);
                        $('#payment-button').click();
                        expectFormSubmitted('#card-number');
                    });

                    it('should validate card type', function() {
                        $('#card-number').val(enRouteCardNumber);
                        $('#payment-button').click();
                        expect($('#card-number~.help-block span').text()).toEqual('Unsupported card type');
                        expect($('.payment-form').attr('data-has-error')).toEqual('true');

                        $('#card-number').val(validCardNumber);
                        $('#payment-button').click();
                        expectFormSubmitted('#card-number');
                    });

                    it('should validate CVN number', function() {
                        var amexCardNumber = '378282246310005',
                            $number = $('#card-number'),
                            $cvn = $('#card-cvn'),
                            $paymentBtn = $('#payment-button');

                        $number.val(amexCardNumber);

                        // American Express cards have a four-digit CVN
                        $cvn.val('123');
                        $paymentBtn.click();
                        expect($cvn.find('~.help-block span').text()).toEqual('Invalid security number');
                        expect($('.payment-form').attr('data-has-error')).toEqual('true');

                        $cvn.val('123b');
                        $paymentBtn.click();
                        expect($cvn.find('~.help-block span').text()).toEqual('Invalid security number');
                        expect($('.payment-form').attr('data-has-error')).toEqual('true');

                        $cvn.val(validCvn);
                        $paymentBtn.click();
                        expectFormSubmitted('#card-cvn');
                    });

                    it('should validate expiry month', function() {
                        $('#card-number').val(validCardNumber);
                        $('#card-cvn').val(validCvn);
                        $('#card-expiry-month').val('99');
                        $('#payment-button').click();
                        expect($('#card-expiry-month~.help-block span').text()).toEqual('Invalid month');
                        expect($('.payment-form').attr('data-has-error')).toEqual('true');

                        $('#card-expiry-month').val('12');
                        $('#payment-button').click();
                        expectFormSubmitted('#card-expiry-month');
                    });

                    it('should validate expiry year', function() {
                        $('#card-number').val(validCardNumber);
                        $('#card-cvn').val(validCvn);
                        $('#card-expiry-month').val('12');
                        $('#card-expiry-year').val('2015');
                        $('#payment-button').click();
                        expect($('#card-expiry-year ~ .help-block span').text()).toEqual('Invalid year');
                        expect($('.payment-form').attr('data-has-error')).toEqual('true');

                        $('#card-expiry-year').val(today.year());
                        $('#payment-button').click();
                        expectFormSubmitted('#card-expiry-year');
                    });

                    it('should validate card expiration', function() {
                        $('#card-number').val(validCardNumber);
                        $('#card-cvn').val(validCvn);
                        $('#card-expiry-month').val(ccExpiryMonths[cardExpirationMonth]);
                        $('#card-expiry-year').val(today.year());
                        $('#payment-button').click();
                        expect($('#card-expiry-month ~ .help-block span').text()).toEqual('Card expired');
                        expect($('.payment-form').attr('data-has-error')).toEqual('true');

                        $('#card-expiry-month').val('12');
                        $('#card-expiry-year').val(today.year());
                        $('#payment-button').click();
                        expectFormSubmitted('#card-expiry-month');
                    });
                });
            });

            describe('onFail', function() {
                it('should report error to message div element', function() {
                    var $errorMessagesDiv;
                    $('<div id="messages"></div>').appendTo('body');
                    $errorMessagesDiv = $('#messages');
                    BasketPage.onFail();
                    expect($errorMessagesDiv.text()).toEqual(
                        'Problem occurred during checkout. Please contact support.'
                    );
                });
            });

            describe('checkoutPayment', function() {
                it('should POST to the checkout endpoint', function() {
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
                beforeEach(function() {
                    spyOn(TrackingModel.prototype, 'isTracking').and.callFake(function() {
                        return true;
                    });
                    spyOn(window.analytics, 'page');
                    spyOn(window.analytics, 'track');
                    AnalyticsUtils.analyticsSetUp();
                    BasketPage.onReady();
                });

                it('should trigger voucher applied analytics event', function() {
                    $('button.apply_voucher').trigger('click');
                    expect(window.analytics.track).toHaveBeenCalledWith(
                        'edx.bi.ecommerce.basket.voucher_applied',
                        {type: 'click'}
                    );
                });

                it('should trigger checkout analytics event', function() {
                    $('button.payment-button').trigger('click');
                    expect(window.analytics.track).toHaveBeenCalledWith(
                        'edx.bi.ecommerce.basket.payment_selected',
                        {category: 'cybersource', type: 'click'}
                    );
                });

                it('should trigger page load analytics event', function() {
                    $('<script type="text/javascript">var initModelData = {};</script>')
                        .appendTo('body');
                    AnalyticsUtils.analyticsSetUp();
                    expect(window.analytics.page).toHaveBeenCalled();
                });
            });

            describe('formatToLocalPrice', function() {
                var EDX_PRICE_LOCATION_COOKIE_NAME = 'edx-price-l10n',
                    USD_VALUE = '1,234.56',
                    ANOTHER_USD_VALUE = '123.45',
                    PREFIX = 'PREFIX',
                    COOKIE_VALUES = {countryCode: 'FOO', rate: 2, code: 'BAR', symbol: 'BAZ'};

                beforeEach(function() {
                    Cookies.remove(EDX_PRICE_LOCATION_COOKIE_NAME);
                });

                afterAll(function() {
                    Cookies.remove(EDX_PRICE_LOCATION_COOKIE_NAME);
                });

                it('should return prefixed price when cookie does not exist', function() {
                    expect(BasketPage.formatToLocalPrice(PREFIX, USD_VALUE)).toEqual(PREFIX + USD_VALUE);
                });

                it('should return prefixed price when country code is USA', function() {
                    Cookies.set(EDX_PRICE_LOCATION_COOKIE_NAME, {countryCode: 'USA'});
                    expect(BasketPage.formatToLocalPrice(PREFIX, USD_VALUE)).toEqual(PREFIX + USD_VALUE);
                });

                it('should return prefixed price when country code is USA', function() {
                    Cookies.set(EDX_PRICE_LOCATION_COOKIE_NAME, {countryCode: 'USA'});
                    expect(BasketPage.formatToLocalPrice(PREFIX, USD_VALUE)).toEqual(PREFIX + USD_VALUE);
                });

                it('should return formatted local price value when non-US cookie exists', function() {
                    Cookies.set(EDX_PRICE_LOCATION_COOKIE_NAME, COOKIE_VALUES);
                    expect(BasketPage.formatToLocalPrice(PREFIX, USD_VALUE)).toEqual('BAZ2,469 BAR *');
                });

                it('should return non-comma separated local price value when non-US cookie exists', function() {
                    Cookies.set(EDX_PRICE_LOCATION_COOKIE_NAME, COOKIE_VALUES);
                    expect(BasketPage.formatToLocalPrice(PREFIX, ANOTHER_USD_VALUE)).toEqual('BAZ247 BAR *');
                });
            });

            describe('generateLocalPriceText', function() {
                it('should replace USD values', function() {
                    spyOn(BasketPage, 'formatToLocalPrice').and.returnValue('foo');
                    expect('foo').toEqual(BasketPage.generateLocalPriceText('USD12.34'));
                    expect(BasketPage.formatToLocalPrice).toHaveBeenCalledWith('USD', '12.34');
                });

                it('should replace $ values', function() {
                    spyOn(BasketPage, 'formatToLocalPrice').and.returnValue('foo');
                    expect('foo').toEqual(BasketPage.generateLocalPriceText('$12.34'));
                    expect(BasketPage.formatToLocalPrice).toHaveBeenCalledWith('$', '12.34');
                });

                it('should replace negative values', function() {
                    spyOn(BasketPage, 'formatToLocalPrice').and.returnValue('foo');
                    expect('-foo').toEqual(BasketPage.generateLocalPriceText('-$12.34'));
                    expect(BasketPage.formatToLocalPrice).toHaveBeenCalledWith('$', '12.34');
                });

                it('should replace commaseparated values', function() {
                    spyOn(BasketPage, 'formatToLocalPrice').and.returnValue('foo');
                    expect('-foo').toEqual(BasketPage.generateLocalPriceText('-$1,234.56'));
                    expect(BasketPage.formatToLocalPrice).toHaveBeenCalledWith('$', '1,234.56');
                });

                it('should only replace currency value', function() {
                    spyOn(BasketPage, 'formatToLocalPrice').and.returnValue('foo');
                    expect('baz -foo bar').toEqual(BasketPage.generateLocalPriceText('baz -$1,234.56 bar'));
                    expect(BasketPage.formatToLocalPrice).toHaveBeenCalledWith('$', '1,234.56');
                });

                it('should not replace text without USD values', function() {
                    var messageWithoutUSDValue = 'This caused a bug';
                    spyOn(BasketPage, 'formatToLocalPrice');
                    expect(messageWithoutUSDValue).toEqual(BasketPage.generateLocalPriceText(messageWithoutUSDValue));
                    expect(BasketPage.formatToLocalPrice).not.toHaveBeenCalled();
                });
            });

            describe('replaceElementText', function() {
                it('should replace text when text does not match', function() {
                    var $element = $('<div />');
                    $element.text('foobar');

                    BasketPage.replaceElementText($element, 'baz');

                    expect($element.text()).toEqual('baz');
                });

                it('should replace not replace price when local price text matches', function() {
                    var $element = $('<div />');
                    $element.text('foobar');

                    BasketPage.replaceElementText($element, 'foobar');

                    expect($element.text()).toEqual('foobar');
                });
            });

            describe('translateToLocalPrices', function() {
                it('should replace prices', function() {
                    var localPriceTextPrefix = 'foobar',
                        priceValues = [
                            '$123.45',
                            '$56.78',
                            '$9.10'
                        ];
                    spyOn(BasketPage, 'generateLocalPriceText').and.callFake(function(usdPriceText) {
                        return localPriceTextPrefix + usdPriceText;
                    });

                    BasketPage.translateToLocalPrices();

                    // 3 .price elements + 3 .voucher elements
                    expect(BasketPage.generateLocalPriceText.calls.count()).toEqual(6);

                    // check to make sure the method was called and conversion occurred
                    $('.price').each(function(index, element) {
                        expect(BasketPage.generateLocalPriceText)
                            .toHaveBeenCalledWith(priceValues[index]);
                        expect($(element).text()).toEqual(localPriceTextPrefix + priceValues[index]);
                    });
                    $('.voucher').each(function(index, element) {
                        expect(BasketPage.generateLocalPriceText)
                            .toHaveBeenCalledWith(priceValues[index]);
                        expect($(element).text()).toEqual(localPriceTextPrefix + priceValues[index]);
                    });
                });

                it('should not replace prices if generate local price text throws', function() {
                    var counter = 0,
                        maxCounterValue = 3,
                        localPriceText = 'foobarbaz',
                        priceValues = [
                            '$123.45',
                            '$56.78',
                            '$9.10'
                        ];

                    spyOn(BasketPage, 'generateLocalPriceText').and.callFake(function() {
                        if (counter >= maxCounterValue) {
                            throw new Error('Test Error');
                        }

                        counter += 1;

                        return localPriceText;
                    });

                    try {
                        BasketPage.translateToLocalPrices();
                    } catch (e) {
                        // Should error while iterating through elements
                        expect(BasketPage.generateLocalPriceText.calls.count()).toEqual(maxCounterValue + 1);

                        // check to make sure element values were not changed
                        $('.price').each(function(index, element) {
                            expect(priceValues[index]).not.toEqual(localPriceText);
                            expect(priceValues[index]).toEqual($(element).text());
                        });

                        $('.voucher').each(function(index, element) {
                            expect(priceValues[index]).not.toEqual(localPriceText);
                            expect(priceValues[index]).toEqual($(element).text());
                        });
                    }
                });
            });

            describe('addPriceDisclaimer', function() {
                var EDX_PRICE_LOCATION_COOKIE_NAME = 'edx-price-l10n';
                var COOKIE_VALUES = {countryCode: 'FOO', rate: 2, code: 'BAR', symbol: 'BAZ'};

                beforeEach(function() {
                    Cookies.remove(EDX_PRICE_LOCATION_COOKIE_NAME);
                });

                afterAll(function() {
                    Cookies.remove(EDX_PRICE_LOCATION_COOKIE_NAME);
                });

                it('should not add disclaimer when cookie is Invalid', function() {
                    spyOn(BasketPage, 'isValidLocalCurrencyCookie').and.returnValue(false);
                    BasketPage.addPriceDisclaimer();
                    expect(0).toEqual($('.price-disclaimer').length);
                });

                it('should return USD price when country code is USA', function() {
                    Cookies.set(EDX_PRICE_LOCATION_COOKIE_NAME, {countryCode: 'USA'});
                    BasketPage.addPriceDisclaimer();
                    expect($('.price-disclaimer').length).toEqual(0);
                });

                it('should return formatted USD when non-US cookie exists', function() {
                    Cookies.set(EDX_PRICE_LOCATION_COOKIE_NAME, COOKIE_VALUES);
                    BasketPage.addPriceDisclaimer();

                    // eslint-disable-next-line max-len
                    expect('* This total contains an approximate conversion. You will be charged $9.10 USD.')
                        .toEqual($('.price-disclaimer').text());
                });
            });

            describe('isValidLocalCurrencyCookie', function() {
                var COOKIE_VALUES = {countryCode: 'FOO', rate: 2, code: 'BAR', symbol: 'BAZ'};

                it('should be invalid if undefined', function() {
                    expect(BasketPage.isValidLocalCurrencyCookie(undefined)).toBe(false);
                });

                it('should be invalid if no country code exists', function() {
                    var cookie = _.clone(COOKIE_VALUES);
                    delete cookie.countryCode;
                    expect(BasketPage.isValidLocalCurrencyCookie(cookie)).toBe(false);
                });

                it('should be invalid if no symbol exists', function() {
                    var cookie = _.clone(COOKIE_VALUES);
                    delete cookie.symbol;
                    expect(BasketPage.isValidLocalCurrencyCookie(cookie)).toBe(false);
                });

                it('should be invalid if no rate exists', function() {
                    var cookie = _.clone(COOKIE_VALUES);
                    delete cookie.rate;
                    expect(BasketPage.isValidLocalCurrencyCookie(cookie)).toBe(false);
                });

                it('should be invalid if no code exists', function() {
                    var cookie = _.clone(COOKIE_VALUES);
                    delete cookie.code;
                    expect(BasketPage.isValidLocalCurrencyCookie(cookie)).toBe(false);
                });

                it('should be valid if cookie exists and all necessary fields exist', function() {
                    var cookie = _.clone(COOKIE_VALUES);
                    expect(BasketPage.isValidLocalCurrencyCookie(cookie)).toBe(true);
                });
            });
        });
    }
);
