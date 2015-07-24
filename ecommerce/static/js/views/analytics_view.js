define([
        'jquery',
        'backbone',
        'underscore'
    ],
    function ($, Backbone, _) {
        'use strict';

        /**
         * This 'view' doesn't display anything, but rather sends tracking
         * information in response to 'segment:track' events triggered by the
         * model.
         *
         * Actions will only be tracked if segmentApplicationId is set in the
         * model.
         */
        return Backbone.View.extend({

            /**
             * Reference to segment.io analytics library.  This is set after
             * loading.
             */

            initialize: function (options) {
                this.options = options || {};

                // wait until you have a segment application ID before kicking
                // up the script
                if (this.model.isTracking()) {
                    this.applicationIdSet();
                } else {
                    this.listenToOnce(this.model, 'change:segmentApplicationId',
                        this.applicationIdSet);
                }
            },

            applicationIdSet: function () {
                var trackId = this.model.get('segmentApplicationId');

                // if no ID is supplied, then don't track
                if (this.model.isTracking()) {
                    // kick off segment
                    this.initSegment(trackId);
                    this.logUser();

                    // now segment has been loaded, we can track events
                    this.listenTo(this.model, 'segment:track', this.track);
                }
            },

            /**
             * This sets up segment.io for our application and loads the initial
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

                // this needs to be called once
                analytics.page(this.buildCourseProperties());
            },

            /**
             * Log the user.
             */
            logUser: function () {
                var userModel = this.options.userModel;
                analytics.identify(userModel.get('username'), {
                    name: userModel.get('name'),
                    email: userModel.get('email')
                });
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

            /**
             * Catch 'segment:track' events and create events and send
             * to segment.io.
             *
             * @param eventType String event type.
             */
            track: function (eventType, properties) {
                var course = this.buildCourseProperties();

                // send event to segment including the course ID
                analytics.track(eventType, _.extend(course, properties));
            }
        });
    }
);
