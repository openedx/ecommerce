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
                'offer/?*queryString': 'showOfferPage'
            /*                
                'offer/?code=:code': 'showOfferPage',
            */
            },

            showOfferPage: function(queryString) {
                var params = this.parseQueryString(queryString);
                var page = new OfferPage({code: params.code, course: params.course, enterprise: params.enterprise});
                this.currentView = page;
                this.$el.html(page.el);
            }
        });
    }
);
