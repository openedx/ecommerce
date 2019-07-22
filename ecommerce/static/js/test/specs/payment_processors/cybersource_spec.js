define(
    [
        'jquery',
        'js-cookie',
        'payment_processors/cybersource'
    ],
    function($,
             Cookies,
             CyberSource) {
        'use strict';

        var $applePayBtn,
            cyberSourceConfig;

        beforeEach(function() {
            jasmine.getFixtures().fixturesPath = '/base/ecommerce/static/js/test/fixtures';
            loadFixtures('client-side-checkout-basket.html');

            cyberSourceConfig = {
                postUrl: 'https://testsecureacceptance.cybersource.com/silent/pay',
                signingUrl: '/payment/cybersource/submit/',
                applePay: {
                    enabled: true,
                    merchantName: 'Open EdX',
                    merchantIdentifier: 'merchant.com.example',
                    countryCode: 'US',
                    basketCurrency: 'USD',
                    basketTotal: '99.00',
                    startSessionUrl: '/payment/cybersource/apple-pay/start-applePaySession/',
                    authorizeUrl: '/payment/cybersource/apple-pay/authorize/',
                    receiptUrl: '/checkout/receipt/'
                }
            };
        });

        afterEach(function() {
            $('body').empty();
        });

        describe('CyberSource', function() {
            describe('init', function() {
                it('should set the action attribute on the payment form', function() {
                    var paymentForm = document.getElementById('paymentForm');
                    expect(paymentForm.getAttribute('action')).toBeNull();

                    CyberSource.init(cyberSourceConfig);
                    expect(paymentForm.getAttribute('action')).toEqual(cyberSourceConfig.postUrl);
                });

                it('should initialize Apple Pay', function() {
                    spyOn(CyberSource, 'initializeApplePay');
                    CyberSource.init(cyberSourceConfig);

                    expect(CyberSource.applePayConfig).toEqual(cyberSourceConfig.applePay);
                    expect(CyberSource.initializeApplePay).toHaveBeenCalled();
                });
            });

            describe('Apple Pay', function() {
                beforeEach(function() {
                    // eslint-disable-next-line no-param-reassign
                    CyberSource.applePayConfig = cyberSourceConfig.applePay;
                    $applePayBtn = $('#applePayBtn');
                    ApplePaySession.stubCanMakePayments = true;
                    ApplePaySession.STATUS_SUCCESS = 0;
                    ApplePaySession.STATUS_FAILURE = 1;
                    expect($applePayBtn).toBeInDOM();
                });

                describe('initializeApplePay', function() {
                    it('should not display the Apple Pay button if the functionality is disabled',
                        function(done) {
                            // eslint-disable-next-line no-param-reassign
                            CyberSource.applePayConfig.enabled = false;

                            CyberSource.initializeApplePay().then(function() {
                                expect($applePayBtn).toBeHidden();
                                done();
                            });
                        }
                    );

                    it('should not display the Apple Pay button if the user has not setup Apple Pay', function(done) {
                        ApplePaySession.stubCanMakePayments = false;
                        CyberSource.initializeApplePay().then(function() {
                            expect($applePayBtn).toBeHidden();
                            done();
                        });
                    });

                    it('should display the Apple Pay button if the user can make payments', function(done) {
                        CyberSource.initializeApplePay().then(function() {
                            expect($applePayBtn).toBeVisible();
                            done();
                        });
                    });
                });

                describe('event handlers', function() {
                    var csrfToken = 'fake-csrf',
                        request,
                        server;

                    beforeEach(function(done) {
                        // eslint-disable-next-line no-undef
                        server = sinon.fakeServer.create({autoRespond: true, respondImmediately: true});
                        Cookies.set('ecommerce_csrftoken', csrfToken);

                        CyberSource.initializeApplePay().then(function() {
                            expect($applePayBtn).toBeVisible();
                            // eslint-disable-next-line no-param-reassign
                            CyberSource.applePaySession = new ApplePaySession(2, {});
                            done();
                        });
                    });

                    afterEach(function() {
                        server.restore();
                    });

                    describe('button click handler', function() {
                        it('should start the Apple Pay session', function() {
                            spyOn(ApplePaySession.prototype, 'begin');
                            $applePayBtn.click();
                            expect(ApplePaySession.prototype.begin).toHaveBeenCalled();
                        });
                    });

                    describe('onApplePayValidateMerchant', function() {
                        var startSessionResponse,
                            // eslint-disable-next-line no-undef
                            event = new ApplePayValidateMerchantEvent('https://g.apple.com/startSession');

                        it('should make an AJAX call to the server', function() {
                            startSessionResponse = {
                                merchantIdentifier: cyberSourceConfig.applePay.merchantIdentifier,
                                domainName: 'example.com',
                                displayName: cyberSourceConfig.applePay.merchantName
                            };

                            spyOn(CyberSource.applePaySession, 'completeMerchantValidation');
                            server.respondWith('POST', cyberSourceConfig.applePay.startSessionUrl,
                                [200, {'Content-Type': 'application/json'}, JSON.stringify(startSessionResponse)]);

                            CyberSource.onApplePayValidateMerchant(event);

                            expect(CyberSource.applePaySession.completeMerchantValidation).toHaveBeenCalledWith(
                                startSessionResponse
                            );

                            expect(server.requests.length).toEqual(1);
                            request = server.requests[0];
                            expect(request.requestHeaders['X-CSRFToken']).toEqual(csrfToken);
                            expect(request.url).toEqual(cyberSourceConfig.applePay.startSessionUrl);
                            expect(JSON.parse(request.requestBody)).toEqual({url: event.validationURL});
                        });

                        it('should display an error if the AJAX call fails', function() {
                            spyOn(CyberSource, 'displayErrorMessage');
                            server.respondWith('POST', cyberSourceConfig.applePay.startSessionUrl,
                                [500, {'Content-Type': 'application/json'}, '{}']);

                            CyberSource.onApplePayValidateMerchant(event);
                            expect(CyberSource.displayErrorMessage).toHaveBeenCalled();
                        });
                    });

                    describe('onApplePayPaymentAuthorized', function() {
                        // eslint-disable-next-line no-undef
                        var event = new ApplePayPaymentAuthorizedEvent({
                            paymentData: {
                                paymentMethod: {
                                    displayName: 'Visa 1111',
                                    network: 'Visa',
                                    type: 'credit'
                                }
                            }
                        });

                        it('should make an AJAX call to the server and redirect to the receipt page on success',
                            function() {
                                var orderNumber = 'EDX-1234',
                                    responseData = {number: orderNumber};

                                spyOn(CyberSource, 'redirectToReceipt');
                                server.respondWith('POST', cyberSourceConfig.applePay.authorizeUrl,
                                    [200, {'Content-Type': 'application/json'}, JSON.stringify(responseData)]);

                                CyberSource.onApplePayPaymentAuthorized(event);
                                expect(CyberSource.redirectToReceipt).toHaveBeenCalledWith(orderNumber);

                                expect(server.requests.length).toEqual(1);
                                request = server.requests[0];
                                expect(request.requestHeaders['X-CSRFToken']).toEqual(csrfToken);
                                expect(request.url).toEqual(cyberSourceConfig.applePay.authorizeUrl);
                                expect(JSON.parse(request.requestBody)).toEqual(event.payment);
                            }
                        );

                        it('should display an error if the AJAX call fails', function() {
                            var responseData = {error: 'failed'};

                            spyOn(CyberSource, 'displayErrorMessage');
                            server.respondWith('POST', cyberSourceConfig.applePay.authorizeUrl,
                                [500, {'Content-Type': 'application/json'}, JSON.stringify(responseData)]);

                            CyberSource.onApplePayPaymentAuthorized(event);
                            expect(CyberSource.displayErrorMessage).toHaveBeenCalled();
                        });
                    });
                });
            });
        });
    });
