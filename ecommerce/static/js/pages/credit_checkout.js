define([
        'jquery',
        'backbone',
        'models/user_model',
        'models/tracking_model',
        'models/course_model',
        'views/clickable_view',
        'views/analytics_view',
        'views/payment_button_view',
        'utils/utils',
        'views/provider_selection_view',
        'pages/page'
    ],
    function ($,
              Backbone,
              UserModel,
              TrackingModel,
              CourseModel,
              ClickableView,
              AnalyticsView,
              PaymentButtonView,
              Utils,
              ProviderSelectionView,
              Page) {
        'use strict';

        return Page.extend({

            initialize: function () {
                var providerSelectionView = new ProviderSelectionView({el: '.provider-details'}),
                    paymentButtonView = new PaymentButtonView({el: '#payment-buttons'});

                this.listenTo(providerSelectionView, 'productSelected', function (data) {
                    paymentButtonView.setSku(data.sku);

                    // Update the display of the checkout total.
                    this.$el.find('.total-price span').text(data.price);
                });

                // Render the payment buttons first, since the rendering of the provider selection will
                // select the first available product.
                paymentButtonView.render();
                providerSelectionView.render();

                var courseModel = new CourseModel(),
                    trackingModel = new TrackingModel(),
                    userModel = new UserModel();

                /* jshint ignore:start */
                // initModelData is set by the Django template at render time.
                trackingModel.set(initModelData.tracking);
                userModel.set(initModelData.user);
                courseModel.set(initModelData.course);
                /* jshint ignore:end */

                /*
                 Triggering the analytics events on clicking the payment buttons on checkoutpage.
                 Buttons has the data-track- attributes type , event and category.
                 */

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
        });
    }
);
