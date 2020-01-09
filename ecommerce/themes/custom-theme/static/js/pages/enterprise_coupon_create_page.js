define([
    'models/enterprise_coupon_model',
    'views/enterprise_coupon_create_edit_view',
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
