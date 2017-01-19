define([
        'backbone.relational'
    ],
    function () {
        'use strict';

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/enterprise/customers',
        });
    }
);
