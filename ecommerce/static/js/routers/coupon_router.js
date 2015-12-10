define([
        'routers/page_router',
        'pages/coupon_list_page',
        'pages/coupon_create_page'
    ],
    function (PageRouter,
              CouponListPage,
              CouponCreatePage) {
        'use strict';

        return PageRouter.extend({

            // Base/root path of the app
            root: '/coupons/',

            routes: {
                '(/)': 'index',
                'new(/)': 'new'
            },

            /**
             * Display a list of all codes in the system.
             */
            index: function () {
                var page = new CouponListPage();
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display a form for creating a new enrollment code.
             */
            new: function () {
                var page = new CouponCreatePage();
                this.currentView = page;
                this.$el.html(page.el);
            }
        });
    }
);
