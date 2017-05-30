require([
    'jquery',
    'dataTablesBootstrap'
],
    function($) {
        'use strict';

        $(function() {
            $('#programOfferTable').DataTable({
                paging: true
            });
        });
    }
);
