define([
    'jquery',
    'views/payment_button_view'
],
    function($,
              PaymentButtonView) {
        'use strict';

        describe('payment button view test', function() {
            var view,
                sku = 'sku-001';


            beforeEach(function() {
                jasmine.getFixtures().fixturesPath = '/base/ecommerce/static/js/test/fixtures';
            });

            beforeEach(function() {
                loadFixtures('checkout.html');
                view = new PaymentButtonView({el: '#payment-buttons'});
                view.render();
                view.setSku(sku);
            });

            it('should have href point to basket view', function() {
                expect(view.$el.find('.payment-button').attr('href')).toEqual('/basket/add/?sku=' + sku);
            });
        });
    }
);
