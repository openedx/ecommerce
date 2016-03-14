define([
        'utils/analytics_utils',
        'pages/page'
    ],
    function (AnalyticsUtils,
              Page) {
        'use strict';

        return Page.extend({
            initialize: function () {
                AnalyticsUtils.analyticsSetUp();
            }
        });
    }
);
