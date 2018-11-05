define([
    'routers/coupon_router',
    'pages/enterprise_coupon_list_page',
    'pages/enterprise_coupon_create_page',
    'pages/enterprise_coupon_detail_page',
    'pages/enterprise_coupon_edit_page'
],
    function(CouponRouter,
              EnterpriseCouponListPage,
              EnterpriseCouponCreatePage,
              EnterpriseCouponDetailPage,
              EnterpriseCouponEditPage) {
        'use strict';

        return CouponRouter.extend({

            // Base/root path of the app
            root: '/enterprise/coupons/',

            getListPage: function() {
                return new EnterpriseCouponListPage();
            },

            getCreatePage: function() {
                return new EnterpriseCouponCreatePage();
            },

            getDetailPage: function(id) {
                return new EnterpriseCouponDetailPage({id: id});
            },

            getEditPage: function(id) {
                return new EnterpriseCouponEditPage({id: id});
            }
        });
    }
);
