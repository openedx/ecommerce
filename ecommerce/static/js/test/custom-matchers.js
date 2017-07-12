define(['jquery'], function($) {
    'use strict';

    beforeEach(function() {
        jasmine.addMatchers({
            toHaveHiddenClass: function() {
                return {
                    compare: function(actual) {
                        return {pass: $(actual).hasClass('hidden')};
                    }
                };
            }
        });
    });
});
