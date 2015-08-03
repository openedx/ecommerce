define([
        'backbone',
        'underscore',
        'backbone.paginator'
    ],
    function (Backbone, _) {
        'use strict';

        return Backbone.PageableCollection.extend({
            queryParams: {
                pageSize: 'page_size'
            },

            state: {
                // TODO Replace this collection with something that works properly with our API.
                pageSize: 10000
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
