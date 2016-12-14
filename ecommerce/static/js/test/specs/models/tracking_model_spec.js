define([
        'underscore',
        'models/tracking_model',
        'test/mock_data/tracking'
    ],
    function (_,
              TrackingModel,
              Mock_Tracking
    ) {
        'use strict';

        var trackingData = Mock_Tracking.trackingData;

        describe('Tracking model', function () {
            describe('isTrackingEnabled', function () {
                it('should return true if Google Analytics tracking is enabled', function () {
                    var model = new TrackingModel(),
                        modelData = _.clone(trackingData);
                    modelData.segmentApplicationId = null;
                    model.set(modelData);

                    expect(model.isTrackingEnabled()).toBe(true);
                });

                it('should return true if Segment tracking is enabled', function () {
                    var model = new TrackingModel(),
                        modelData = _.clone(trackingData);
                    modelData.googleAnalyticsTrackingIds = [];
                    model.set(modelData);

                    expect(model.isTrackingEnabled()).toBe(true);
                });

                it('should return false if Google Analytics and Segment tracking are not enabled', function () {
                    var model = new TrackingModel();
                    model.set({
                        googleAnalyticsTrackingIds: [],
                        segmentApplicationId: null
                    });

                    expect(model.isTrackingEnabled()).toBe(false);
                });
            });

            describe('isGoogleAnalyticsTrackingEnabled', function () {
                it('should return true if Google Analytics tracking is enabled', function () {
                    var model = new TrackingModel();
                    model.set(trackingData);

                    expect(model.isGoogleAnalyticsTrackingEnabled()).toBe(true);
                });

                it('should return false if Google Analytics tracking is not enabled', function () {
                    var model = new TrackingModel();
                    model.set({
                        googleAnalyticsTrackingIds: []
                    });

                    expect(model.isGoogleAnalyticsTrackingEnabled()).toBe(false);
                });
            });

            describe('isSegmentTrackingEnabled', function () {
                it('should return true if Segment tracking is enabled', function () {
                    var model = new TrackingModel();
                    model.set(trackingData);

                    expect(model.isSegmentTrackingEnabled()).toBe(true);
                });

                it('should return false if Segment tracking is not enabled', function () {
                    var model = new TrackingModel();
                    model.set({
                        segmentApplicationId: null
                    });

                    expect(model.isSegmentTrackingEnabled()).toBe(false);
                });
            });
        });
    }
);
