define([
        'backbone',
        'js/models/provider_model'
    ],
    function (Backbone, ProviderModel) {
        'use strict';

        return Backbone.Collection.extend({
                model: ProviderModel,
                url: lmsRootUrl + '/api/credit/v1/providers/',
                setUrl: function (providerIds) {
                    this.url += '?provider_ids=' + providerIds;
                }
            }
        );
    }
);
