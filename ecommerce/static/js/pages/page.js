define(['backbone',
    'backbone.super',
    'underscore',
    'utils/utils'],
    function(Backbone,
             BackboneSuper,
             _,
             Utils) {
        'use strict';

        /** *
         * Base Page class.
         */
        var Page = Backbone.View.extend({
            /**
             * Document title set during rendering.
             *
             * This can either be a string or a function that accepts this
             * instance and returns a string.
             */
            title: null,

            /**
             * Initializes this view and any models, collections, and/or nested views.
             *
             * Inheriting classes MUST override this method.
             */
            initialize: function() {

            },

            /**
             * Removes the nested view before removing this view.
             */
            remove: function() {
                if (this.view) {
                    this.view.remove();
                    this.view = null;
                }

                return this._super(); // eslint-disable-line no-underscore-dangle
            },

            /**
             * Updates the browser window's title.
             */
            renderTitle: function() {
                var title = _.result(this, 'title');

                if (title) {
                    document.title = title;
                }
            },

            /**
             * Renders the nested view.
             */
            renderNestedView: function() {
                this.view.render();
                this.$el.html(this.view.el);
            },

            /**
             * Renders this Page, specifically the title and nested view.
             * @returns {Page} current instance
             */
            render: function() {
                Utils.toogleMobileMenuClickEvent();
                this.renderTitle();
                this.renderNestedView();
                return this;
            },

            refresh: function() {
                this.view.remove();
                this.render();
            }
        });

        return Page;
    }
);
