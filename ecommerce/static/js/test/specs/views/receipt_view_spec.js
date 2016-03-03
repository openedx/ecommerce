define([
        'jquery',
        'views/receipt_view'
    ],
    function ($, ReceiptView) {
        'use strict';

        describe('receipt view', function() {
            var mockRender, orderResponseData, providerResponseData, partnerResponseData, verificationData,
                receiptView, view;

            mockRender = function(isVerified) {

                $('#receipt-container').data('verified', isVerified);
                receiptView = new ReceiptView();
                receiptView.orderId = 'EDX-123456';

                spyOn($, 'ajax').and.callFake(function (callback) {
                     callback.success(verificationData);
                });

                spyOn(receiptView, 'getReceiptData').and.callFake(function() {
                      return {
                        then: function (callback) {
                            return callback(orderResponseData);
                        }
                    };
                });
                spyOn(receiptView, 'getPartnerData').and.callFake(function() {
                      return {
                        then: function (callback) {
                            return callback(partnerResponseData);
                        }
                    };
                });
                spyOn(receiptView, 'getProviderData').and.callFake(function() {
                      return {
                        then: function (callback) {
                            return callback(providerResponseData);
                        }
                    };
                });
                receiptView.render();
                return receiptView;
            };

            beforeEach(function() {
                $('<div class="container"><div id="error-container" class="hidden"></div>' +
                  '<div id="receipt-container" class="pay-and-verify hidden" ' +
                  '</div></div>').appendTo('body');
                $('#receipt-container').data({
                    'is-payment-complete': true,
                    'platformName': 'edX',
                    'username': 'Test User',
                    'lms-url': 'https://www.edx.org'
                });
                // Test rendering a portion of the UnderScore template after receiving order information.
                $('head').append('<script type="text/template" id="receipt-tpl">' +
                '<span class="order-number-heading">Order Number:</span>' +
                '<div class="order-info"><%- receipt.orderNum %></div>' +
                '<span class="order-payment-heading">Payment Method:</span>' +
                '<div class="order-info"><%- receipt.paymentProcessor %></div>' +
                '<div class="addressed-to"><address>\n' +
                '<% for ( var i = 0; i < receipt.shipping_address.length; i++ ) { %>\n' +
                '<%- receipt.shipping_address[i] %> <br/>\n' +
                '<% } %>\n' +
                '</address></div>\n' +
                '<div class="billed-to"><address>\n' +
                '<span class="name-first"><%- receipt.billedTo.firstName %></span>'+
                '<span class="address-city"><%- receipt.billedTo.city %></span>' +
                '</address></div>\n' +
                '<div class="partner"></div>' +
                '<div class="voucher-info"><span class="voucher-code"><%- receipt.vouchers[0].code %>' +
                '<%- receipt.discountPercentage %>% off</span><span class="discount">-<%- receipt.currency %>' +
                '<%- receipt.discount %></span></div>' +
                '<span class="value-amount"><%- receipt.totalCost %></span>' +
                '<div class="hidden" id="receipt-provider"></div></script>\n' +
                '<script type="text/template" id="provider-tpl"><div class="provider-more-info">' +
                'To finalize course credit, <%- display_name %> requires <%- platformName %> credit request.' +
                '<button id="credit-button">Get Credit</button>' +
                '</div></script>\n');
                orderResponseData = {
                    'status': 'Open',
                    'billing_address': {
                        'city': 'dummy city',
                        'first_name': 'john',
                        'last_name': 'doe',
                        'country': 'AL',
                        'line2': 'line2',
                        'line1': 'line1',
                        'state': 'MA',
                        'postcode': '12345'
                    },
                    'user': {
                        'email': 'test@example.com',
                        'username': 'Test'
                    },
                    'lines': [
                        {
                            'status': 'Open',
                            'unit_price_excl_tax': '10.00',
                            'product': {
                                'attribute_values': [
                                    {
                                        'name': 'certificate_type',
                                        'value': 'verified'
                                    },
                                    {
                                        'name': 'course_key',
                                        'code': 'course_key',
                                        'value': 'course-v1:edx+dummy+2015_T3'
                                    },
                                    {
                                        'name': 'credit_provider',
                                        'value': 'edx'
                                    }
                                ],
                                'stockrecords': [
                                    {
                                        'price_currency': 'USD',
                                        'product': 123,
                                        'partner_sku': '1234ABC',
                                        'partner': 1,
                                        'price_excl_tax': '10.00',
                                        'id': 123
                                    }
                                ],
                                'product_class': 'Seat',
                                'title': 'Dummy title',
                                'url': 'https://ecom.edx.org/api/v2/products/123/',
                                'price': '10.00',
                                'expires': null,
                                'is_available_to_buy': true,
                                'id': 123,
                                'structure': 'child'
                            },
                            'line_price_excl_tax': '5.00',
                            'description': 'dummy description',
                            'title': 'dummy title',
                            'quantity': 1
                        }
                    ],
                    'number': 'EDX-123456',
                    'date_placed': '2016-01-01T01:01:01Z',
                    'currency': 'USD',
                    'total_excl_tax': '5.00',
                    'shipping_address': [
                        'Ms Joyce Zhu',
                        '141 Portland Street',
                        'Cambridge, MA 12345',
                        'US'
                    ],
                    'vouchers': [
                        {
                            'id': 1,
                            'name': 'Test_Coupon',
                            'code': 'ABC123UANDME',
                            'redeem_url': 'https://ecommerce-edx.org/coupons/offer/?code=ABC123UANDME',
                            'usage': 'Multi-use',
                            'start_datetime': '2016-07-25T00:00:00Z',
                            'end_datetime': '2016-08-13T00:00:00Z',
                            'num_basket_additions': 0,
                            'num_orders': 1,
                            'total_discount': '5.00',
                            'date_created': '2016-07-25',
                            'offers': [
                                1
                            ],
                            'is_available_to_user': [
                                true,
                                ''
                            ],
                            'benefit': {
                                'type': 'Absolute',
                                'value': 5
                            }
                        }
                    ],
                   'payment_processor': 'paypal',
                   'discount': '5.00'
                };

                partnerResponseData = {
                    'id': 1,
                    'name': 'Open edX',
                    'short_code': 'edX',
                    'catalogs': 'https://ecom.edx.org/api/v2/partners/1/catalogs/',
                    'products': 'https://ecom.edx.org/api/v2/partners/1/products/'
                };

                providerResponseData = {
                    'id': 'edx',
                    'display_name': 'edX',
                    'url': 'http://www.edx.org',
                    'status_url': 'http://www.edx.org/status',
                    'description': 'Nothing',
                    'enable_integration': false,
                    'fulfillment_instructions': '',
                    'thumbnail_url': 'http://edx.org/thumbnail.png'
                };

                verificationData = {
                    'is_verification_required': true
                };
            });

            afterEach(function () {
                $('#receipt-tpl').remove();
                $('body').empty();
            });

            it('renders receipt order information with verified course', function() {
                view = mockRender('True');
                expect(view.$('.order-number-heading').next().text()).toContain('EDX-123456');
                expect(view.$('.value-amount').text()).toContain('5.00');
            });

            it('renders receipt order information with non-verified course', function() {
                view = mockRender('False');
                expect(view.$('.order-number-heading').next().text()).toContain('EDX-123456');
                expect(view.$('.value-amount').text()).toContain('5.00');
            });

            it('renders receipt when not given a provider ID', function () {
                view = new ReceiptView();
                view.orderId = 'EDX-123456';
                var order_without_provider = {
                    'status': 'Open',
                    'user': {
                        'email': 'test@example.com',
                        'username': 'Test'
                    },
                    'billing_address': {
                        'city': 'dummy city',
                        'first_name': 'john'
                    },
                    'lines': [
                        {
                            'status': 'Open',
                            'unit_price_excl_tax': '10.00',
                            'product': {
                                'attribute_values': [
                                    {
                                        'name': 'certificate_type',
                                        'value': 'verified'
                                    },
                                    {
                                        'name': 'course_key',
                                        'code': 'course_key',
                                        'value': 'course-v1:edx+dummy+2015_T3'
                                    },
                                    {
                                        'name': 'id_verification_required',
                                        'code': 'id_verification_required',
                                        'value': true
                                    }
                                ],
                                'stockrecords': [
                                    {
                                        'price_currency': 'USD',
                                        'product': 123,
                                        'partner_sku': '1234ABC',
                                        'partner': 1,
                                        'price_excl_tax': '10.00',
                                        'id': 123
                                    }
                                ],
                                'product_class': 'Seat',
                                'title': 'Dummy title',
                                'url': 'https://ecom.edx.org/api/v2/products/123/',
                                'price': '10.00',
                                'expires': null,
                                'is_available_to_buy': true,
                                'id': 123,
                                'structure': 'child'
                            },
                            'line_price_excl_tax': '5.00',
                            'description': 'dummy description',
                            'title': 'dummy title',
                            'quantity': 1
                        }
                    ],
                    'number': 'EDX-123456',
                    'date_placed': '2016-01-01T01:01:01Z',
                    'currency': 'USD',
                    'total_excl_tax': '5.00',
                    'shipping_address': [],
                    'vouchers': [{'code': 'qwerty'}],
                   'payment_processor': 'paypal',
                   'discount': '5.00'
               };
                spyOn($, 'ajax').and.callFake(function(params) {
                    params.success(verificationData);
                });
                spyOn(view, 'getReceiptData').and.callFake(function() {
                      return {
                        then: function (callback) {
                            return callback(order_without_provider);
                        }
                    };
                });
                spyOn(view, 'getPartnerData').and.callFake(function() {
                      return {
                        then: function (callback) {
                            return callback(partnerResponseData);
                        }
                    };
                });
                view.render();
                expect($('.order-number-heading').next().text()).toContain('EDX-123456');
            });
            
            it('renders an error banner when not given an order ID', function() {
                view = new ReceiptView();
                spyOn(view, 'renderError').and.callThrough();
                view.render();
                expect(view.renderError).toHaveBeenCalled();
                expect($('#error-container').hasClass('hidden')).toBeFalsy();
            });



            it('renders partner information given an order number', function () {
                view = mockRender('True');
                expect(view.$('.partner').text()).toContain('Open edX');
            });

            it('renders payment processor information', function() {
                view = mockRender('True');
                expect(view.$('.order-payment-heading').next().text()).toContain('paypal');
            });

            it('renders provider information', function() {
                view = mockRender('True');
                expect(view.$('.provider-more-info').text()).toContain('edX');
            });

            it('renders shipping address information', function() {
                view = mockRender('True');
                expect(view.$('.addressed-to').text()).toContain('Ms Joyce Zhu');
                expect(view.$('.addressed-to').text()).toContain('141 Portland Street');
                expect(view.$('.addressed-to').text()).toContain('Cambridge, MA 12345');
            });

            it('renders billing address information', function(){
                view = mockRender('True');
                expect(view.$('.name-first').text()).toContain('john');
                expect(view.$('.address-city').text()).toContain('dummy city');
            });
            
            it('renders voucher code and discount information', function() {
                view = mockRender('True');
                expect(view.$('.voucher-code').text()).toContain('ABC123UANDME');
                expect(view.$('.voucher-code').text()).toContain('50% off');
                expect(view.$('.discount').text()).toContain('5.00');
            });

            it('allows learners to go through credit process to complete order', function() {
                view = new ReceiptView();
                $('<div class="hidden" id="receipt-provider"></div>').appendTo('#receipt-container');
                view.orderId = 'EDX-123456';
                view.renderProvider({
                    'platformName': 'edX',
                    'username': 'Test',
                    'courseKey': 'course123',
                    'display_name': 'edX'
                });
                console.log($('#credit-button').html());
                // Clear ajax spy from getting verification status to handle button click
                // this.removeAllSpies();
                //$.ajax.reset();
                spyOn(view, 'getCredit').and.callThrough();
                view.delegateEvents();
                view.$('#credit-button').click();
                expect(view.getCredit).toHaveBeenCalled();
            });

            it('handles malformed order data without an associated course key', function(){
               view = new ReceiptView();
               view.orderId = 'EDX-123456';
               var malformedOrder = {
                   'lines': [
                        {
                            'status': 'Open',
                            'unit_price_excl_tax': '10.00',
                            'product': {
                                'attribute_values': [
                                    {
                                        'name': 'certificate_type',
                                        'value': 'verified'
                                    }
                                ],
                                'stockrecords': [
                                    {
                                        'price_currency': 'USD',
                                        'product': 123,
                                        'partner_sku': '1234ABC',
                                        'partner': 1,
                                        'price_excl_tax': '10.00',
                                        'id': 123
                                    }
                                ],
                                'product_class': 'Seat',
                                'title': 'Dummy title',
                                'url': 'https://ecom.edx.org/api/v2/products/123/',
                                'price': '10.00',
                                'expires': null,
                                'is_available_to_buy': true,
                                'id': 123,
                                'structure': 'child'
                            },
                            'line_price_excl_tax': '5.00',
                            'description': 'dummy description',
                            'title': 'dummy title',
                            'quantity': 1
                        }
                    ]
               };
               expect(view.getOrderCourseKey(malformedOrder)).toEqual(null);
            });

            it('handles data without a credit provider id', function(){
               view = new ReceiptView();
               view.orderId = 'EDX-123456';
               var order_without_provider = {
                    'status': 'Open',
                    'user': {
                        'email': 'test@example.com',
                        'username': 'Test'
                    },
                    'lines': [
                        {
                            'status': 'Open',
                            'unit_price_excl_tax': '10.00',
                            'product': {
                                'attribute_values': [
                                    {
                                        'name': 'certificate_type',
                                        'value': 'verified'
                                    },
                                    {
                                        'name': 'course_key',
                                        'code': 'course_key',
                                        'value': 'course-v1:edx+dummy+2015_T3'
                                    }
                                ],
                                'stockrecords': [
                                    {
                                        'price_currency': 'USD',
                                        'product': 123,
                                        'partner_sku': '1234ABC',
                                        'partner': 1,
                                        'price_excl_tax': '10.00',
                                        'id': 123
                                    }
                                ],
                                'product_class': 'Seat',
                                'title': 'Dummy title',
                                'url': 'https://ecom.edx.org/api/v2/products/123/',
                                'price': '10.00',
                                'expires': null,
                                'is_available_to_buy': true,
                                'id': 123,
                                'structure': 'child'
                            },
                            'line_price_excl_tax': '5.00',
                            'description': 'dummy description',
                            'title': 'dummy title',
                            'quantity': 1
                        }
                    ],
                    'number': 'EDX-123456',
                    'date_placed': '2016-01-01T01:01:01Z',
                    'currency': 'USD',
                    'total_excl_tax': '5.00'
               };
               spyOn(view, 'renderProvider');
               spyOn(view, 'getProviderData');
               spyOn(view, 'renderError');
               view.render();
               expect(view.getProviderData).not.toHaveBeenCalled();
               expect(view.renderProvider).not.toHaveBeenCalled();
               expect(view.renderError).not.toHaveBeenCalled();
               expect(view.getCreditProviderId(order_without_provider)).toEqual(null);
            });
        });
    }
);
