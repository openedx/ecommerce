define([
        'jquery',
        'views/form_view',
        'text!templates/program/program_form.html',
    ],
    function ($,
              FormView,
              ProgramFormTemplate) {
        'use strict';

        return FormView.extend({
            tagName: 'form',

            className: 'program-form-view',

            template: _.template(ProgramFormTemplate),

            initialize: function (options) {
                this.editing = options.editing || false;

                this._super();
            },

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template(this.model.attributes));

                this._super();
                return this;
            },
        });
    }
);
