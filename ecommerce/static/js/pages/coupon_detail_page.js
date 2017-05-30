define([
    'models/coupon_model',
    'views/coupon_detail_view',
    'pages/page'
],
    function(Coupon,
              CouponDetailView,
              Page) {
        'use strict';

        return Page.extend({
            title: function() {
                return this.model.get('title') + ' - ' + gettext('View Coupon');
            },

            initialize: function(options) {
                this.model = Coupon.findOrCreate({id: options.id});
                this.view = new CouponDetailView({model: this.model});
                this.listenTo(this.model, 'sync', this.refresh);
                this.model.fetch();
            }
        });
    }
);
