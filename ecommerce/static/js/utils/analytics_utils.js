define([
    'jquery',
    'backbone',
    'backbone.validation',
    'underscore',
    'utils/utils',
    'models/user_model',
    'models/tracking_model',
    'views/clickable_view',
    'views/analytics_view'
],
    function($,
              Backbone,
              BackboneValidation,
              _,
              Utils,
              UserModel,
              TrackingModel,
              ClickableView,
              AnalyticsView) {
        'use strict';

        return {
            analyticsSetUp: function() {
                var trackingModel = new TrackingModel(),
                    userModel = new UserModel();

                /* eslint-disable */
                // initModelData is set by the Django template at render time.
                trackingModel.set(initModelData.tracking);
                userModel.set(initModelData.user);
                /* eslint-enable*/

                new AnalyticsView({
                    model: trackingModel,
                    userModel: userModel
                });

                // instrument the click events
                _($('[data-track-type="click"]')).each(function(track) {
                    var properties = Utils.getNodeProperties(track.attributes,
                        'data-track-', ['data-track-event']);
                    new ClickableView({
                        model: trackingModel,
                        trackEventType: $(track).attr('data-track-event'),
                        trackProperties: properties,
                        el: track
                    });
                });
            }
        };
    }
);
