require([
    'jquery',
    'pikaday'
],
    function($, Pikaday) {
        'use strict';

        $(function() {
            $('#offerForm').find('.add-pikaday').each(function() {
                new Pikaday({
                    field: this,
                    format: 'YYYY-MM-DD HH:mm:ss',
                    setDefaultDate: false,
                    showTime: true,
                    use24hour: false,
                    autoClose: false
                });
            });
        });
    }
);
