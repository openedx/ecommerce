define([
    'models/coupon_model',
    'views/coupon_create_edit_view',
    'pages/page'
],
    function(Coupon,
              CouponCreateEditView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Create New Coupon'),

            initialize: function() {
                this.model = new Coupon();
                this.view = new CouponCreateEditView({model: this.model});
                this.render();
            }
        });
    }
);
