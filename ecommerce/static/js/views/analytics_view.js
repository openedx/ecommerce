/* global analytics */
define([
    'jquery',
    'backbone'
],
    function($, Backbone) {
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
             * Reference to Segment analytics library.  This is set after
             * loading.
             */

            initialize: function(options) {
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

            applicationIdSet: function() {
                var trackId = this.model.get('segmentApplicationId');

                // if no ID is supplied, then don't track
                if (this.model.isTracking()) {
                    // kick off segment
                    this.initSegment(trackId);
                    this.logUser();
                    analytics.page();

                    // now segment has been loaded, we can track events
                    this.listenTo(this.model, 'segment:track', this.track);
                }
            },

            /**
             * This sets up Segment for our application
             *
             * this.segment is set for convenience.
             */
            initSegment: function(applicationKey) {
                var analytics;

                // jscs:disable
                // eslint-disable-next-line
                analytics = window.analytics = window.analytics || []; if (!analytics.initialize) if (analytics.invoked)window.console && console.error && console.error('Segment snippet included twice.'); else { analytics.invoked = !0; analytics.methods = ['trackSubmit', 'trackClick', 'trackLink', 'trackForm', 'pageview', 'identify', 'group', 'track', 'ready', 'alias', 'page', 'once', 'off', 'on']; analytics.factory = function(t) { return function() { var e = Array.prototype.slice.call(arguments); e.unshift(t); analytics.push(e); return analytics; }; }; for (var t = 0; t < analytics.methods.length; t++) { var e = analytics.methods[t]; analytics[e] = analytics.factory(e); }analytics.load = function(t) { var e = document.createElement('script'); e.type = 'text/javascript'; e.async = !0; e.src = (document.location.protocol === 'https:' ? 'https://' : 'http://') + 'cdn.segment.com/analytics.js/v1/' + t + '/analytics.min.js'; var n = document.getElementsByTagName('script')[0]; n.parentNode.insertBefore(e, n); }; analytics.SNIPPET_VERSION = '3.0.1'; }
                // jscs:enable

                // provide our application key for logging
                analytics.load(applicationKey);
            },

            /**
             * Log the user.
             */
            logUser: function() {
                var userModel = this.options.userModel;
                analytics.identify(
                    userModel.get('user_tracking_id'),
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
            },

          /**
           * Catch 'segment:track' events and create events and send
           * to Segment.
           *
           * @param eventType String event type.
           * @param properties Event properties.
           */
            track: function(eventType, properties) {
                // https://segment.com/docs/sources/website/analytics.js/#track
                analytics.track(eventType, properties);
            }
        });
    }
);
