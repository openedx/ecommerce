define([
    'routers/page_router',
    'pages/coupon_list_page',
    'pages/coupon_create_page',
    'pages/coupon_detail_page',
    'pages/coupon_edit_page'
],
    function(PageRouter,
              CouponListPage,
              CouponCreatePage,
              CouponDetailPage,
              CouponEditPage) {
        'use strict';

        return PageRouter.extend({

            // Base/root path of the app
            root: '/coupons/',

            routes: {
                '(/)': 'index',
                'new(/)': 'new',
                ':id(/)': 'show',
                ':id/edit(/)': 'edit',
                '*path': 'notFound'
            },

            /**
             * Display a list of all codes in the system.
             */
            index: function() {
                var page = new CouponListPage();
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display a form for creating a new enrollment code.
             */
            new: function() {
                var page = new CouponCreatePage();
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display details for a single coupon.
             * @param {String} id - ID of the coupon to display.
             */
            show: function(id) {
                var page = new CouponDetailPage({id: id});
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display a form for editing an existing coupon.
             */
            edit: function(id) {
                var page = new CouponEditPage({id: id});
                this.currentView = page;
                this.$el.html(page.el);
            }
        });
    }
);
