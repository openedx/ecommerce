define([
        'backbone',
        'backbone.validation',
        'underscore',
        'utils/utils',
        'models/user_model',
        'models/tracking_model',
        'models/course_model',
        'views/clickable_view',
        'views/analytics_view',],
    function (Backbone,
              BackboneValidation,
              _,
              Utils,
              UserModel,
              TrackingModel,
              CourseModel,
              ClickableView,
              AnalyticsView) {
        'use strict';

        return {
            analyticsSetUp: function() {
                var courseModel = new CourseModel(),
                    trackingModel = new TrackingModel(),
                    userModel = new UserModel();

                /* jshint ignore:start */
                // initModelData is set by the Django template at render time.
                trackingModel.set(initModelData.tracking);
                userModel.set(initModelData.user);
                courseModel.set(initModelData.course);
                /* jshint ignore:end */

                new AnalyticsView({
                    model: trackingModel,
                    userModel: userModel,
                    courseModel: courseModel
                });

                // instrument the click events
                _($('[data-track-type="click"]')).each(function (track) {
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
