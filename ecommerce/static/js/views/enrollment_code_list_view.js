define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/enrollment_code_list.html',
        'dataTablesBootstrap'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              EnrollmentCodeListViewTemplate) {

        'use strict';

        return Backbone.View.extend({
            className: 'enrollment-code-list-view',

            template: _.template(EnrollmentCodeListViewTemplate),

            initialize: function () {

            },

            render: function () {
                this.$el.html(this.template);
                return this;
            }
        });
    }
);
