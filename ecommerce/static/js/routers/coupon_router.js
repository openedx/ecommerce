define([
        'backbone',
        'backbone.route-filter',
        'backbone.super',
        'pages/coupon_list_page',
        'pages/coupon_create_page'
    ],
    function (Backbone,
              BackboneRouteFilter,
              BackboneSuper,
              CouponListPage,
              CouponCreatePage) {
        'use strict';

        return Backbone.Router.extend({
            // Keeps track of the page/view currently on display
            currentView: null,

            // Base/root path of the app
            root: '/coupons/',

            routes: {
                '(/)': 'index',
                'new(/)': 'new',
                '*path': 'notFound'
            },

            // Filter(s) called before routes are executed. If the filters return a truthy value
            // the route will be executed; otherwise, the route will not be executed.
            before: {
                '*any': 'clearView'
            },

            /**
             * Setup special routes.
             *
             * @param {Object} options - Data used to initialize the router. This should include a key, $el, that
             * refers to a jQuery Element where the pages will be rendered.
             */
            initialize: function (options) {
                // This is where views will be rendered
                this.$el = options.$el;
            },

            /**
             * Starts the router.
             */
            start: function () {
                Backbone.history.start({pushState: true, root: this.root});
                return this;
            },

            /**
             * Removes the current view.
             */
            clearView: function () {
                if (this.currentView) {
                    this.currentView.remove();
                    this.currentView = null;
                }

                return this;
            },

            /**
             * 404 page
             * @param {String} path - Invalid path.
             */
            notFound: function (path) {
                // TODO Render something!
                alert(path + ' is invalid.');
            },

            /**
             * Display a list of all codes in the system.
             */
            index: function () {
                var page = new CouponListPage();
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display a form for creating a new enrollment code.
             */
            new: function () {
                var page = new CouponCreatePage();
                this.currentView = page;
                this.$el.html(page.el);
            }
        });
    }
);
