require([
        'backbone',
        'collections/category_collection',
        'ecommerce',
        'routers/coupon_router',
        'utils/navigate',
    ],
    function (Backbone,
              CategoryCollection,
              ecommerce,
              CouponRouter,
              navigate) {
        'use strict';

        $(function () {
            var $app = $('#app'),
                couponApp = new CouponRouter({$el: $app});

            ecommerce.coupons = ecommerce.coupons || {};
            ecommerce.coupons.categories = new CategoryCollection();
            ecommerce.coupons.categories.url = '/api/v2/coupons/categories/';
            ecommerce.coupons.categories.fetch({ async: false });
            couponApp.start();

            // Handle navbar clicks.
            $('a.navbar-brand').on('click', navigate);

            // Handle internal clicks
            $app.on('click', 'a', navigate);
        });
    }
);
