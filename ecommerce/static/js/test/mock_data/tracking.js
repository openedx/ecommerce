define([], function () {
    'use strict';

    var courseData = {
            courseId: 'test_course_id'
        },
        trackingData = {
            googleAnalyticsTrackingIds: ['test_ga_tracking_id_1', 'test_ga_tracking_id_2'],
            segmentApplicationId: 'test_segment_key'
        },
        userData = {
            username: 'test_user',
            name: 'test test',
            email: 'test@example.com'
        };
    return {
        'courseData': courseData,
        'trackingData': trackingData,
        'userData': userData
    };
});
