define([
        'jquery',
        'backbone',
        'backbone.super',
        'underscore',
        'views/enrollment_codes_form_view',
        'text!templates/enrollment_codes_create.html',
        'bootstrap'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              _,
              EnrollmentCodesFormView,
              EnrollmentCodesCreateTemplate) {
        'use strict';

        return Backbone.View.extend({
            template: _.template(EnrollmentCodesCreateTemplate),
            className: 'enrollment-codes-create-view',

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
                this.formView = this.formView || new EnrollmentCodesFormView();

                // Render the basic page layout
                $html = $(this.template());

                // Render the form
                this.formView.render();
                $html.find('.enrollment-codes-form-outer').html(this.formView.el);

                // Render the complete view
                this.$el.html($html);

                // Activate the tooltips
                this.$el.find('[data-toggle="tooltip"]').tooltip();

                return this;
            }
        });
    }
);
