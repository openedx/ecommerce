require(['jquery', 'dataTablesBootstrap'], function($) {

    $(document).ready(function() {

        var $table = $('#courseTable').DataTable({
            "info": false,
            "paging": false,
            "oLanguage": {
                "sSearch": ''
            }
        });

        $('#courseTable_filter input').attr('placeholder', gettext('Filter by org or course ID'));
   });

});
