define([
    'models/coupon_model',
    'pages/page',
    'views/coupon_create_edit_view'
],
    function(Coupon,
              Page,
              CouponCreateEditView) {
        'use strict';

        return Page.extend({
            title: function() {
                return this.model.get('title') + ' - ' + gettext('Edit Coupon');
            },

            initialize: function(options) {
                this.model = Coupon.findOrCreate({id: options.id});
                this.view = new CouponCreateEditView({
                    editing: true,
                    model: this.model
                });

                this.listenTo(this.model, 'sync', this.render);
                this.model.fetch();
            }
        });
    }
);
