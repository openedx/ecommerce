define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/code_list.html',
        'dataTablesBootstrap'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              codeListViewTemplate) {

        'use strict';

        return Backbone.View.extend({
            className: 'code-list-view',

            template: _.template(codeListViewTemplate),

            initialize: function () {

            },

            render: function () {
                this.$el.html(this.template);
                return this;
            }
        });
    }
);
