define([
    'views/coupon_list_view',
    'pages/page'
],
    function(CouponListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Coupon Codes'),

            initialize: function() {
                this.view = new CouponListView();
                this.render();
            }
        });
    }
);
