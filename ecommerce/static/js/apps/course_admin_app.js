require([
        'backbone',
        'routers/course_router',
        'collections/credit_provider_collection',
        'ecommerce'
    ],
    function (Backbone,
              CourseRouter,
              CreditProviderCollection,
              ecommerce) {
        'use strict';

        var navigate,
            courseApp;

        /**
         * Navigate to a new page within the app.
         *
         * Attempts to open the link in a new tab/window behave as the user expects, however the app
         * and data will be reloaded in the new tab/window.
         *
         * @param {Event} event - Event being handled.
         * @returns {boolean} - Indicates if event handling succeeded (always true).
         */
        navigate = function (event) {
            var url = $(this).attr('href').replace(courseApp.root, '');

            // Handle the cases where the user wants to open the link in a new tab/window.
            if (event.ctrlKey || event.shiftKey || event.metaKey || event.which === 2) {
                return true;
            }

            // We'll take it from here...
            event.preventDefault();

            // Process the navigation in the app/router.
            if (url === Backbone.history.getFragment() && url === '') {
                // Note: We must call the index directly since Backbone does not support routing to the same route.
                courseApp.index();
            } else {
                courseApp.navigate(url, {trigger: true});
            }
        };

        /**
         * Navigate to a new page within the Course App.
         *
         * This extends Backbone.View, allowing pages to navigate to
         * any path within the app, without requiring a reference to the
         * app instance.
         *
         * @param {String} fragment
         */
        Backbone.View.prototype.goTo = function (fragment) {
            courseApp.navigate(fragment, {trigger: true});
        };

        $(function () {
            var $app = $('#app');

            ecommerce.credit = ecommerce.credit || {};
            ecommerce.credit.providers = new CreditProviderCollection($app.data('credit-providers'));

            courseApp = new CourseRouter({$el: $app});
            courseApp.start();

            // Handle navbar clicks.
            $('a.navbar-brand').on('click', navigate);

            // Handle internal clicks
            $app.on('click', 'a', navigate);
        });
    }
);
