define([
    'backbone',
    'underscore.string',
    'models/credit_provider'
],
    function(Backbone,
              _s,
              CreditProvider) {
        'use strict';

        return Backbone.Collection.extend({
            model: CreditProvider,

                /**
                 * Initializes the collection.
                 *
                 * @param {Object} options This Object MUST contain lmsRootUrl and providerIds keys.
                 */
            initialize: function(options) {
                if (options) {
                    this.lmsRootUrl = options.lmsRootUrl;
                    this.providerIds = options.providerIds;
                }
            },

                /**
                 * Returns the URL where provider data should be retrieved.
                 * @returns {String}
                 */
            url: function() {
                var data = {
                    root: this.lmsRootUrl,
                    providerIds: this.providerIds
                };

                return _s.sprintf('%(root)s/api/credit/v1/providers/?provider_ids=%(providerIds)s', data);
            }
        }
        );
    }
);
