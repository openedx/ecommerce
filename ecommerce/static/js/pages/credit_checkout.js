require([
        'jquery',
        'backbone',
        'js/models/user-model',
        'js/models/tracking-model',
        'js/models/course-model',
        'js/views/clickable-view',
        'js/views/analytics_view',
        'js/views/payment_button_view',
        'js/utils/utils',
        'js/views/provider_view'
    ],
    function( $,Backbone, UserModel, TrackingModel, CourseModel, ClickableView, AnalyticsView, PaymentButtonView, Utils, ProviderView ) {

        new PaymentButtonView({
           el: $( '#payment-buttons' )
        });

        new ProviderView({
           el: $( '.provider-details' )
        });

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
);
