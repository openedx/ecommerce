define([
        'backbone',
        'underscore',
        'backbone.paginator'
    ],
    function (Backbone, _) {
        'use strict';

        return Backbone.PageableCollection.extend({
            state: {
                pageSize: 20
            },

            parseRecords: function (resp, options) {
                return resp.results;
            },


            parseState: function (resp, queryParams, state, options) {
                return {
                    totalRecords: resp.count
                };
            },

            parseLinks: function (resp, options) {
                return {
                    first: null,
                    next: resp.next,
                    prev: resp.previous
                };
            }
        });
    }
);
