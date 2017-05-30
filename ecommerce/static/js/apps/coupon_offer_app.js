require([
    'jquery',
    'pages/coupon_offer_page'
],
    function($,
              CouponOfferPage) {
        'use strict';

        new CouponOfferPage({el: $('#offer')});
    }
);
