define([
    'underscore',
    'views/coupon_create_edit_view',
    'views/enterprise_coupon_form_view',
    'text!templates/enterprise_coupon_create_edit.html',
    'bootstrap'
],
    function(_,
              CouponCreateEditView,
              EnterpriseCouponFormView,
              EnterpriseCouponCreateEditTemplate) {
        'use strict';

        return CouponCreateEditView.extend({
            template: _.template(EnterpriseCouponCreateEditTemplate),

            getFormView: function() {
                return this.formView || new EnterpriseCouponFormView({editing: this.editing, model: this.model});
            }
        });
    }
);
