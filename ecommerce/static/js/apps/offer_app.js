require([
    'jquery',
    'routers/offer_router'
],
    function($,
              OfferRouter) {
        'use strict';

        $(function() {
            var $app = $('#offerApp'),
                offerApp = new OfferRouter({$el: $app});
            offerApp.start();
        });
    }
);

