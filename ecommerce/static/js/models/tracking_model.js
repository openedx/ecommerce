define(['backbone', 'underscore'], function(Backbone, _) {
    'use strict';

    /**
     * Stores our tracking logic and information.
     */
    return Backbone.Model.extend({

        isTrackingEnabled: function() {
            return this.isGoogleAnalyticsTrackingEnabled() || this.isSegmentTrackingEnabled();
        },

        isGoogleAnalyticsTrackingEnabled: function() {
            var trackingIds = this.get('googleAnalyticsTrackingIds');
            return Boolean(!_(trackingIds).isUndefined() && trackingIds.length);
        },

        isSegmentTrackingEnabled: function() {
            var trackId = this.get('segmentApplicationId');
            return Boolean(!_(trackId).isUndefined() && trackId);
        }

    });
});
