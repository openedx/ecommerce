require([
        'jquery',
        'backbone',
        'backbone-super',
        'bootstrap',
        'bootstrap_accessibility',
        'underscore'
    ],
    function () {
        $(function () {
            $('[data-toggle="tooltip"]').tooltip();
        })
    });
