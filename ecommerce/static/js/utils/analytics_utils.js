define([
        'backbone',
        'backbone.validation',
        'underscore',
        'utils/utils',
        'models/user_model',
        'models/tracking_model',
        'models/course_model',
        'views/clickable_view',
        'views/analytics_view'],
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
            courseModel: new CourseModel(),
            trackingModel: new TrackingModel(),
            userModel: new UserModel(),

            analyticsSetUp: function() {

                /* jshint ignore:start */
                // initModelData is set by the Django template at render time.
                this.trackingModel.set(initModelData.tracking);
                this.userModel.set(initModelData.user);
                this.courseModel.set(initModelData.course);
                /* jshint ignore:end */

                new AnalyticsView({
                    model: this.trackingModel,
                    userModel: this.userModel,
                    courseModel: this.courseModel
                });

                console.log(JSON.stringify(this.trackingModel));

                this.instrumentClickEvents();
            },

            instrumentClickEvents: function() {
                var self = this;
                // instrument the click events
                _($('[data-track-type="click"]')).each(function (track) {
                    var properties = Utils.getNodeProperties(track.attributes,
                        'data-track-', ['data-track-event']);
                    new ClickableView({
                        model: self.trackingModel,
                        trackEventType: $(track).attr('data-track-event'),
                        trackProperties: properties,
                        el: track
                    });
                });
            }
        };
    }
);
