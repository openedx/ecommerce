define([
        'jquery',
        'underscore',
        'views/analytics_view',
        'models/course_model',
        'test/mock_data/tracking',
        'models/tracking_model',
        'models/user_model'
    ],
    function ($,
              _,
              AnalyticsView,
              CourseModel,
              Mock_Tracking,
              TrackingModel,
              UserModel
    ) {
        'use strict';

        describe('analytics view', function() {
            var view,
                trackingModel,
                courseModel = new CourseModel(Mock_Tracking.courseData),
                userModel = new UserModel(Mock_Tracking.userData),
                TEST_EVENT = {
                    courseId: courseModel.get('courseId'),
                    category: 'test_category'
                },
                EXPECTED_GA_CALLS= [];
            for (var i = 0; i < Mock_Tracking.trackingData.googleAnalyticsTrackingIds.length; i++) {
                EXPECTED_GA_CALLS.push({
                    object: window,
                    args: [
                        'tracker' + i + '.send',
                        {
                            hitType: 'event',
                            eventCategory: TEST_EVENT.category,
                            eventAction: 'test'
                        }
                    ],
                    returnValue: undefined
                });
            }

            describe('track with Segment and GA configured', function() {
                beforeEach(function() {
                    trackingModel = new TrackingModel(Mock_Tracking.trackingData);
                    view = new AnalyticsView({
                        model: trackingModel,
                        courseModel: courseModel,
                        userModel: userModel
                    });
                    view.initialize(view.options);
                    view.loadGoogleAnalytics(Mock_Tracking.trackingData.googleAnalyticsTrackingIds);

                    spyOn(window.analytics, 'track');
                    spyOn(window, 'ga');

                    view.track('test', TEST_EVENT);
                });

                it('should send events to the configured segment source', function () {
                    expect(window.analytics.track).toHaveBeenCalledWith('test', TEST_EVENT);
                });

                it('should send events to all configured ga tracking IDs', function () {
                    expect(window.ga.calls.all()).toEqual(EXPECTED_GA_CALLS);
                });
            });

            describe('track with only GA configured', function() {
                beforeEach(function() {
                    var trackingData = _.clone(Mock_Tracking.trackingData);
                    delete trackingData.segmentApplicationId;
                    trackingModel = new TrackingModel(trackingData);
                    view = new AnalyticsView({
                        model: trackingModel,
                        courseModel: courseModel,
                        userModel: userModel
                    });
                    view.initialize(view.options);

                    spyOn(window, 'ga');

                    view.track('test', TEST_EVENT);
                });

                it('should send events to all configured ga tracking IDs', function () {
                    expect(window.ga.calls.all()).toEqual(EXPECTED_GA_CALLS);
                });
            });
        });
    }
);
