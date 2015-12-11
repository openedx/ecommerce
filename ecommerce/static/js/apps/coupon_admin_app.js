require([
        'backbone',
        'routers/coupon_router',
        'utils/navigate'
    ],
    function (Backbone,
              CouponRouter,
              navigate) {
        'use strict';

        $(function () {
            var $app = $('#app'),
                couponApp = new CouponRouter({$el: $app});

            couponApp.start();

            // Handle navbar clicks.
            $('a.navbar-brand').on('click', navigate);

            // Handle internal clicks
            $app.on('click', 'a', navigate);
        });
    }
);
