define([
    'jquery',
    'underscore',
    'views/alert_view'],
    function($,
             _,
             AlertView) {
        'use strict';

        return {
             /**
              * Remove all alerts currently on display.
              *
              * @param {View} context - View from which all alerts are removed.
              */
            clearAlerts: function(context) {
                _.each(context.alertViews, function(view) {
                    view.remove();
                });

                context.alertViews = []; // eslint-disable-line no-param-reassign

                return context;
            },

            /**
             * Renders alerts that will appear at the top of the page.
             *
             * @param {String} level - Severity of the alert. This should be one of success, info, warning, or danger.
             * @param {String} title - Part of the message in <strong></strong> tag.
             * @param {String} message - Message to display to the user.
             * @param {View} context - View which renders the alert.
             */
            renderAlert: function(level, title, message, context) {
                var view = new AlertView({level: level, title: title, message: message});

                view.render();
                context.$alerts.append(view.el);
                context.alertViews.push(view);

                $('body').animate({
                    scrollTop: context.$alerts.offset().top
                }, 500);

                context.$alerts.focus();

                return context;
            }
        };
    }
);
