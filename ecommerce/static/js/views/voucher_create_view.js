define([
        'jquery',
        'backbone',
        'backbone.super',
        'underscore',
        'views/voucher_form_view',
        'text!templates/voucher_create.html',
        'bootstrap'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              _,
              VoucherFormView,
              VoucherCreateTemplate) {
        'use strict';

        return Backbone.View.extend({
            template: _.template(VoucherCreateTemplate),
            className: 'voucher-create-view',

            remove: function () {
                if (this.formView) {
                    this.formView.remove();
                    this.formView = null;
                }

                this._super();
            },

            render: function () {
                var $html;

                // The form should be instantiated only once.
                this.formView = this.formView || new VoucherFormView();

                // Render the basic page layout
                $html = $(this.template());

                // Render the form
                this.formView.render();
                $html.find('.voucher-form-outer').html(this.formView.el);

                // Render the complete view
                this.$el.html($html);

                // Activate the tooltips
                this.$el.find('[data-toggle="tooltip"]').tooltip();

                return this;
            }
        });
    }
);
