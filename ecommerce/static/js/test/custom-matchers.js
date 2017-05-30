define(['jquery'], function($) {
    'use strict';

    beforeEach(function() {
        jasmine.addMatchers({
            /**
             * Returns a Boolean value that indicates whether an element is visible,
             * which it can't be if it's not in the DOM or is hidden.
             */
            toBeVisible: function() {
                return {
                    compare: function(actual) {
                        return {pass: ($(actual).length > 0 && !$(actual).hasClass('hidden'))};
                    }
                };
            },

            /**
             * Returns a Boolean value that indicates whether a DOM element has a specific class.
             */
            toHaveClass: function() {
                return {
                    compare: function(actual, className) {
                        return {pass: $(actual).hasClass(className)};
                    }
                };
            }
        });
    });
});
