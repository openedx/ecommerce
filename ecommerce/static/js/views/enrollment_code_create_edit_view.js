define([
        'jquery',
        'backbone',
        'backbone.super',
        'underscore',
        'views/enrollment_code_form_view',
        'text!templates/enrollment_code_create_edit.html',
        'bootstrap'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              _,
              EnrollmentCodeFormView,
              EnrollmentCodeCreateEditTemplate) {
        'use strict';

        return Backbone.View.extend({
            template: _.template(EnrollmentCodeCreateEditTemplate),
            className: 'enrollment-code-create-edit-view',

            initialize: function (options) {
                // This indicates if we are editing or creating a code.
                this.editing = options.editing;
            },

            remove: function () {
                if (this.formView) {
                    this.formView.remove();
                    this.formView = null;
                }

                this._super();
            },

            render: function () {
                var $html,
                    data = this.model.attributes;

                // The form should be instantiated only once.
                this.formView = this.formView || new EnrollmentCodeFormView({editing: this.editing, model: this.model});

                // Render the basic page layout
                data.editing = this.editing;
                $html = $(this.template(data));

                // Render the form
                this.formView.render();
                $html.find('.enrollment-code-form-outer').html(this.formView.el);

                // Render the complete view
                this.$el.html($html);

                // Activate the tooltips
                this.$el.find('[data-toggle="tooltip"]').tooltip();

                return this;
            }
        });
    }
);
