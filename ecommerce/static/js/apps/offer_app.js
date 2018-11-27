require([
    'jquery',
    'routers/offer_router',
    'ecommerce'
],
    function($,
              OfferRouter,
              ecommerce) {
        'use strict';

        $(function() {
            var $app = $('#offerApp'),
                offerApp = new OfferRouter({$el: $app});

            ecommerce.currency = {
                currencyCode: $app.data('currency-code'),
                currencySymbol: $app.data('currency-symbol')
            };
            offerApp.start();
        });
    }
);

