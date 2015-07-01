require(['jquery', 'dataTablesBootstrap'], function ($) {
    $(document).ready(function () {


        var filter_placeholder = gettext('Filter by org or course ID'),
            $empty_label = $('<label>').addClass('sr-only').html(filter_placeholder);

        $('#courseTable').DataTable({
            "info": false,
            "paging": false,
            "oLanguage": {
                "sSearch": ''
            }
        });

        $('#courseTable_filter label').prepend($empty_label);

        $('#courseTable_filter input')
            .attr('placeholder', filter_placeholder)
            .addClass('field-input input-text')
            .removeClass('form-control input-sm');
    });
});
