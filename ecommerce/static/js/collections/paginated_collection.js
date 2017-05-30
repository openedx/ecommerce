define([
    'backbone'
],
    function(Backbone) {
        'use strict';

        return Backbone.Collection.extend({
            parse: function(response) {
                // Continue retrieving the remaining data
                if (response.next) {
                    this.url = response.next;
                    this.fetch({remove: false});
                }
                return response.results;
            }
        });
    }
);
