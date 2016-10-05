define([
        'jquery',
        'backbone',
        'underscore.string',
        'utils/analytics_utils',
        'js-cookie',
        'views/receipt_view'
    ],
    function ($,
              Backbone,
              _s,
              AnalyticsUtils,
              Cookies,
              ReceiptView) {
        'use strict';

        describe('receipt view', function () {
            var orderNumber,
                view;

            beforeEach(function () {
                $('body').append('<div id="receipt-container" data-is-payment-complete="True"></div>');
                orderNumber = 'ORDER01';
                view = new ReceiptView({ orderNumber: orderNumber});
            });

            it('Receipt page instance should have order number upon initialization', function () {
                expect(view.orderNumber).toBe(orderNumber);
            });

            it('Receipt page should track Purchase upon rendering Order data', function () {
                spyOn(AnalyticsUtils, 'instrumentClickEvents');
                spyOn(view, 'trackPurchase');
                view.render();
                expect(AnalyticsUtils.instrumentClickEvents).toHaveBeenCalled();
                expect(view.trackPurchase).toHaveBeenCalled();
            });

            it('Receipt page should get Order Data from Orders API endpoint before triggering event', function () {
                spyOn($, 'ajax');
                view.trackPurchase();
                expect($.ajax).toHaveBeenCalledWith({
                    url: _s.sprintf('/api/v2/orders/%s', orderNumber),
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': Cookies.get('ecommerce_csrftoken')
                    },
                    success: view.triggerCompletedPurchase
                });
            });

            it('Receipt page should trigger Segment.io event named Completed Purchase', function () {
                var data = {
                    currency: '$',
                    number: orderNumber,
                    total_excl_tax: 100
                };
                spyOn(AnalyticsUtils.trackingModel, 'trigger');
                view.triggerCompletedPurchase(data);
                expect(AnalyticsUtils.trackingModel.trigger).toHaveBeenCalledWith(
                    'segment:track',
                    'Completed Purchase',
                    {
                        currency: data.currency,
                        orderId: data.number,
                        total: data.total_excl_tax
                    }
                );
            });
        });
    }
);
