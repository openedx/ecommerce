define([
    'views/enterprise_coupon_list_view',
    'pages/page'
],
    function(CouponListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Enterprise Coupon Codes'),

            initialize: function() {
                this.view = new CouponListView();
                this.render();
            }
        });
    }
);
