require([
        'jquery',
        'backbone',
        'bootstrap',
        'bootstrap_accessibility',
        'underscore'
    ],
    function () {
        'use strict';

        $(function () {
            // Activate all pre-rendered tooltips.
            $('[data-toggle="tooltip"]').tooltip();
        });
    }
);
