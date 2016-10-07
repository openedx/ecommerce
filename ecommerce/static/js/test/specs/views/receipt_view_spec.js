define([
        'jquery',
        'views/receipt_view'
    ],
    function ($, ReceiptView) {
        'use strict';

        describe('receipt view', function() {
            var mockRender,
                orderResponseData,
                providerResponseData,
                partnerResponseData,
                receiptView,
                verificationData,
                view;

            mockRender = function(isVerified) {
                $('#receipt-container').data('verified', isVerified);
                receiptView = new ReceiptView({orderNumber: 'EDX-123456'});

                spyOn($, 'ajax').and.callFake(function (callback) {
                     callback.success(verificationData);
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

            it('renders an error banner when not given an order ID', function() {
                view = new ReceiptView({});
                spyOn(view, 'renderError').and.callThrough();
                view.render();
                expect(view.renderError).toHaveBeenCalled();
                expect($('#error-container').hasClass('hidden')).toBeFalsy();
            });
        });
    }
);
