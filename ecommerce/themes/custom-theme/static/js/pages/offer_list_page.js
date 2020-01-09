require([
    'jquery',
    'dataTablesBootstrap'
],
    function($) {
        'use strict';

        $(function() {
            $('#offerTable').DataTable({
                paging: true
            });
        });
    }
);
