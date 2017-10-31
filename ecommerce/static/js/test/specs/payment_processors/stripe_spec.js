define([
        'jquery',
        'payment_processors/stripe',
    ],
    function($,
             StripeProcessor) {
        'use strict';
        var stripeStub,
            stripeConfig = {
            postUrl: 'https://example.com/submit/',
            publishableKey: 'pk_test_js',
            country: 'US',
            paymentRequest: {
                currency: 'usd',
                label: 'Open edX Testing',
                total: '100'
            }
        };

        beforeEach(function() {
            stripeStub = jasmine.createSpyObj('Stripe', ['setPublishableKey']);
            window.Stripe = stripeStub;
            jasmine.getFixtures().fixturesPath = '/base/ecommerce/static/js/test/fixtures';
            loadFixtures('client-side-checkout-basket.html');
        });

        describe('Stripe processor', function() {
            describe('init', function() {
                it('should set the publishable key on the Stripe client', function(){
                    // FIXME This fails due to the call: Stripe(token). We can't mock the constructor!
                    StripeProcessor.init(stripeConfig);
                    expect(stripeStub.setPublishableKey).toHaveBeenCalled();
                });
            });
        });
    }
);
