define([
        'collections/coupon_collection',
        'views/coupon_list_view',
        'pages/page'
    ],
    function (CouponCollection,
              CouponListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Coupon Codes'),

            initialize: function () {
                this.collection = new CouponCollection();
                this.view = new CouponListView({collection: this.collection});
                this.render();
                this.collection.fetch({remove: false, data: {page_size: 50}});
            }
        });
    }
);
