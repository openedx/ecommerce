// jscs:disable requireCapitalizedConstructors

define([
        'backbone',
        'backbone.relational',
        'backbone.super',
        'backbone.validation',
        'jquery',
        'jquery-cookie',
        'moment',
        'underscore',
        'utils/utils'
    ],
    function (Backbone,
              BackboneRelational,
              BackboneSuper,
              BackboneValidation,
              $,
              $cookie,
              moment,
              _,
              Utils) {
        'use strict';

        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/codes/',

            defaults: {
            },

            validation: {
            },

            labels: {
            },

            relations: [{

            }],


            initialize: function () {

            },

            parse: function (response) {
                response = this._super(response);
                return response;
            },

            toJSON: function () {
                var data = this._super();
                return data;
            },

            save: function (options) {

            }
        });
    }
);
