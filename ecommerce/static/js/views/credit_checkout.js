require([
        'jquery',
        'js/views/payment_button_view'
    ],
    function( $, PaymentButtonView ) {
        var paybtnview = new PaymentButtonView({
           el: $( '#payment-buttons')
        });
    }
);
