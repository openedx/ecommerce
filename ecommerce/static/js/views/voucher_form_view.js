// jscs:disable requireCapitalizedConstructors

define([
        'jquery',
        'backbone',
        'backbone.super',
        'backbone.validation',
        'backbone.stickit',
        'moment',
        'underscore',
        'underscore.string',
        'collections/course_collection',
        'text!templates/voucher_form.html'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              moment,
              _,
              _s,
              CourseCollection,
              VoucherFormTemplate) {
        'use strict';

        return Backbone.View.extend({
            tagName: 'form',

            className: 'voucher-form-view',

            template: _.template(VoucherFormTemplate),

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template());

                return this;
            }
        });
    }
);
