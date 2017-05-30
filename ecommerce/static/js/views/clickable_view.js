define(['underscore', 'backbone'],
    function(_, Backbone) {
        'use strict';

        /**
         * Use this for triggering track events when an element is clicked.
         * 'segment:track' and an event are fired when the element is clicked.
         */
        return Backbone.View.extend({

            initialize: function(options) {
                var self = this;
                self.options = options;

                if (_(self.options).has('trackEventType')) {
                    self.render();
                }
            },

            render: function() {
                var self = this;

                // track the click
                self.$el.click(function() {
                    // track this event type along with properties
                    self.model.trigger('segment:track',
                        self.options.trackEventType,
                        self.options.trackProperties);
                });
                return this;
            }
        });
    }
);
