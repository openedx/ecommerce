require([
        'jquery',
        'backbone',
        'bootstrap',
        'bootstrap_accessibility',
        'underscore'
    ],
    function () {
        $(function () {
            // Activate all pre-rendered tooltips.
            $('[data-toggle="tooltip"]').tooltip();
        })
    }
);
