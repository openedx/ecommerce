define(['underscore', 'backbone'],
    function (_, Backbone) {
        'use strict';

        /**
         * Use this for triggering track events a user leaves the page.
         * 'segment:track' and an event are fired when the element is clicked.
         */
        return Backbone.View.extend({

            logLeaving: function() {
                var userModel = this.options.userModel;

                window.onbeforeunload = function(e) {
                    analytics.page('Leaving', {
                        user: userModel.get('username'),
                    });
                }
            },

            initialize: function (options) {
                this.options = options || {};
                var analytics;
                analytics = window.analytics || [];
                this.logLeaving();
            },
        });
    }
);
