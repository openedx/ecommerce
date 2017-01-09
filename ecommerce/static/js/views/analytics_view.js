/* globals ga */
define([
        'jquery',
        'backbone',
        'underscore'
    ],
    function ($, Backbone, _) {
        'use strict';

        /**
         * This 'view' doesn't display anything, but rather sends tracking
         * information in response to 'analytics:track' events triggered by the
         * model.
         *
         * Actions will only be tracked if analytics providers have been configured.
         */
        return Backbone.View.extend({

            initialize: function (options) {
                this.options = options || {};
                this.googleAnalyticsTrackers = [];

                // wait until you have a segment application ID before kicking
                // up the script
                if (this.model.isTrackingEnabled()) {
                    this.initTracking();
                } else {
                    this.listenToOnce(this.model, 'change:segmentApplicationId', this.initTracking);
                }
            },

            initTracking: function () {
                var segmentKey = this.model.get('segmentApplicationId');
                var googleAnalyticsTrackingIds = this.model.get('googleAnalyticsTrackingIds');

                if (this.model.isSegmentTrackingEnabled()) {
                    this.initSegment(segmentKey);
                }
                
                if (this.model.isGoogleAnalyticsTrackingEnabled()) {
                    this.initGoogleAnalytics(googleAnalyticsTrackingIds);
                }
                
                if (this.model.isTrackingEnabled()) {
                    this.listenTo(this.model, 'analytics:track', this.track);
                    this.logUser();
                    this.sendPageView();
                }
            },

            /**
             * Create a Google Analytics tracker for each configured tracking ID.
             */
            initGoogleAnalyticsTrackers: function(trackingIds) {
                for (var t = 0; t < trackingIds.length; t++) {
                    var trackingId = trackingIds[t],
                        trackerName = 'tracker' + t;
                    ga('create', trackingId, 'auto', trackerName);
                    this.googleAnalyticsTrackers.push(trackerName);
                }
            },

            /**
             * This sets up Google Analytics tracking for the application.
             */
            initGoogleAnalytics: function (trackingIds) {
                if (this.model.isSegmentTrackingEnabled()) {
                    var self = this;
                    analytics.ready(function(){
                        self.loadGoogleAnalytics(trackingIds);
                    });
                } else {
                    this.loadGoogleAnalytics(trackingIds);
                }
            },

            /**
             * This loads Google Analytics analytics.js library.
             */
            loadGoogleAnalytics: function (trackingIds) {
                if (typeof ga === 'undefined') {
                    // Load Google Analytics analytics.js library
                    (function(i, s, o, g, r, a, m) {
                        i.GoogleAnalyticsObject = r;
                        i[r] = i[r] || function() {
                            (i[r].q = i[r].q || []).push(arguments);
                        };
                        i[r].l = 1 * new Date();
                        a = s.createElement(o);
                        m = s.getElementsByTagName(o)[0];
                        a.async = 1;
                        a.src = g;
                        m.parentNode.insertBefore(a, m);
                    })(window, document, 'script', 'https://www.google-analytics.com/analytics.js', 'ga');
                }
                this.initGoogleAnalyticsTrackers(trackingIds);
            },

            /**
             * This sets up Segment for our application and loads the initial
             * page load.
             *
             * this.segment is set for convenience.
             */
            initSegment: function (applicationKey) {
                /* jshint ignore:start */
                // jscs:disable
                var analytics = window.analytics = window.analytics||[];if(!analytics.initialize)if(analytics.invoked)window.console&&console.error&&console.error("Segment snippet included twice.");else{analytics.invoked=!0;analytics.methods=["trackSubmit","trackClick","trackLink","trackForm","pageview","identify","group","track","ready","alias","page","once","off","on"];analytics.factory=function(t){return function(){var e=Array.prototype.slice.call(arguments);e.unshift(t);analytics.push(e);return analytics}};for(var t=0;t<analytics.methods.length;t++){var e=analytics.methods[t];analytics[e]=analytics.factory(e)}analytics.load=function(t){var e=document.createElement("script");e.type="text/javascript";e.async=!0;e.src=("https:"===document.location.protocol?"https://":"http://")+"cdn.segment.com/analytics.js/v1/"+t+"/analytics.min.js";var n=document.getElementsByTagName("script")[0];n.parentNode.insertBefore(e,n)};analytics.SNIPPET_VERSION="3.0.1";}
                // jscs:enable
                /* jshint ignore:end */

                // provide our application key for logging
                analytics.load(applicationKey);
            },

            /**
             * Get data for initializing segment.
             */
            getSegmentPageData: function () {
                if (this.options.courseModel.get('courseId')) {
                    return this.buildCourseProperties();
                }

                return {};
            },

            /**
             * Log the user.
             */
            logUser: function() {
                var userModel = this.options.userModel;
                if (this.model.isSegmentTrackingEnabled()) {
                    analytics.identify(
                        userModel.get('username'),
                        {
                            name: userModel.get('name'),
                            email: userModel.get('email')
                        },
                        {
                            integrations: {
                                // Disable MailChimp because we don't want to update the user's email
                                // and username in MailChimp based on this request. We only need to capture
                                // this data in MailChimp on registration/activation.
                                MailChimp: false
                            }
                        }
                    );
                }

                if (this.model.isGoogleAnalyticsTrackingEnabled()) {
                    for (var t = 0; t < this.googleAnalyticsTrackers.length; t++) {
                        ga(this.googleAnalyticsTrackers[t] + '.set', 'userId', userModel.get('username'));
                    }
                }
            },

            /**
             * Send page view event.
             */
            sendPageView: function() {
                if (this.model.isSegmentTrackingEnabled()) {
                    analytics.page(this.getSegmentPageData());
                }

                if (this.model.isGoogleAnalyticsTrackingEnabled()) {
                    for (var t = 0; t < this.googleAnalyticsTrackers.length; t++) {
                        ga(this.googleAnalyticsTrackers[t] + '.send', 'pageview');
                    }
                }
            },

            buildCourseProperties: function() {
                var course = {};

                if (this.options.courseModel) {
                    course.courseId = this.options.courseModel.get('courseId');
                }

                if (this.model.has('page')) {
                    course.label = this.model.get('page');
                }

                return course;
            },

            buildGoogleAnalyticsEventProperties: function(eventAction, properties) {
                return {
                    hitType: 'event',
                    eventCategory: properties.category,
                    eventAction: eventAction
                };
            },

            /**
             * Catch 'analytics:track' events and send them to analytics providers.
             *
             * @param eventType String event type.
             */
            track: function (eventType, properties) {
                if (this.model.isSegmentTrackingEnabled()) {
                    // Send event to segment including the course ID
                    analytics.track(eventType, _.extend(this.buildCourseProperties(), properties));
                }

                if (this.model.isGoogleAnalyticsTrackingEnabled()) {
                    // Send event to Google Analytics properties
                    for (var t = 0; t < this.googleAnalyticsTrackers.length; t++) {
                        ga(
                            this.googleAnalyticsTrackers[t] + '.send',
                            this.buildGoogleAnalyticsEventProperties(eventType, properties)
                        );
                    }
                }
            }
        });
    }
);
