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
        'text!templates/enrollment_codes_form.html'
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
              EnrollmentCodesFormTemplate) {
        'use strict';

        return Backbone.View.extend({
            tagName: 'form',

            className: 'enrollment-codes-form-view',

            template: _.template(EnrollmentCodesFormTemplate),

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template());

                return this;
            }
        });
    }
);
