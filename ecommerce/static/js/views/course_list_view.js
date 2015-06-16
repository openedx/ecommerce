require(['jquery', 'dataTablesBootstrap'], function($) {

    $(document).ready(function() {

        var $table = $('#courseTable').DataTable({
            "info": false,
            "paging": false,
            "oLanguage": {
                "sSearch": ''
            }
        });

        $('#courseTable_filter input').attr('placeholder', 'Filter by org or course ID');
   });

});
