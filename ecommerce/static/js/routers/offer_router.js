define([
        'routers/page_router',
        'pages/offer_page'
    ],
    function (PageRouter,
              OfferPage) {
        'use strict';

        return PageRouter.extend({

            // Base/root path of the app
            root: '/coupons/',

            routes: {
                'offer/?code=:code': 'showOfferPage'
            },

            showOfferPage: function(code) {
                var page = new OfferPage({code: code});
                this.currentView = page;
                this.$el.html(page.el);
            }
        });
    }
);
