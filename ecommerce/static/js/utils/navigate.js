define([
    'backbone'
],
    function(Backbone) {
        'use strict';

        /**
         * Navigate to a new page within the app.
         *
         * Attempts to open the link in a new tab/window behave as the user expects, however the app
         * and data will be reloaded in the new tab/window.
         *
         * @param {Event} event - Event being handled.
         * @returns {boolean} - Indicates if event handling succeeded (always true).
         */
        return function(event) {
            var url = $(this).attr('href').replace(Backbone.history.root, '');

            // Handle the cases where the user wants to open the link in a new tab/window.
            if (event.ctrlKey || event.shiftKey || event.metaKey || event.which === 2) {
                return true;
            }

            // We'll take it from here...
            event.preventDefault();

            // Process the navigation in the app/router.
            if (url === Backbone.history.getFragment() && url === '') {
                // Backbone's history/router will do nothing when trying to load the same URL.
                // Force the route instead.
                Backbone.history.loadUrl(url);
            } else {
                Backbone.history.navigate(url, {trigger: true});
            }

            return undefined;
        };
    }
);
