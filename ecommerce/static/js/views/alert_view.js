define([
    'jquery',
    'backbone',
    'underscore'
],
    function($, Backbone, _) {
        'use strict';

        return Backbone.View.extend({
            className: 'alert',
            template: _.template('<strong><%= title %></strong> <%= message %>'),

            initialize: function(options) {
                this.level = options.level || 'info';
                this.title = options.title || '';
                this.message = options.message || '';
            },

            render: function() {
                var body = this.template({title: this.title, message: this.message});
                this.$el.addClass('alert-' + this.level).attr('role', 'alert').html(body);
                return this;
            }
        });
    }
);
