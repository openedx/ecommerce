define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/enrollment_codes_list.html'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              enrollmentCodesListViewTemplate) {

        'use strict';

        return Backbone.View.extend({
            className: 'enrollment-codes-list-view',

            template: _.template(enrollmentCodesListViewTemplate),

            render: function () {
                this.$el.html(this.template);

                return this;
            },
        });
    }
);
