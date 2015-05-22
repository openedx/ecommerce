$(document).ready(function () {
    var $actions = $('[data-action=process-refund]');

    var processRefund = function (e) {
        var $btn = $(e.target),
            refund_id = $btn.data('refund-id'),
            decision = $btn.data('decision');

        // Disable button
        e.preventDefault();
        $btn.addClass('disabled');
        $btn.unbind('click');

        // Make AJAX call and update status
        $.ajax({
            url: '/api/v2/refunds/' + refund_id + '/process/',
            data: { action: decision },
            method: 'PUT',
            headers: {'X-CSRFToken': $.cookie('csrftoken')}
        }).success(function (data) {
            $('tr[data-refund-id=' + refund_id + '] .refund-status').text(data.status);
            addMessage('alert-success', 'icon-check-sign', 'Refund #' + refund_id + ' has been processed.');
            $actions.remove();
        }).fail(function (jqXHR, textStatus, errorThrown) {
            // NOTE (RFL): For an MVP, changing the displayed refund state on any error may be viable.
            // Ideally, the displayed refund state would only change if the refund were to enter an
            // error state. This would be easiest if the processing endpoint returned 200 and a serialized
            // refund, even when the refund has entered an error state during processing.
            $('tr[data-refund-id=' + refund_id + '] .refund-status').text('Error');

            addMessage(
                'alert-error',
                'icon-exclamation-sign',
                'Failed to process refund #' + refund_id + ': ' + errorThrown + '. Please try again, or contact the E-Commerce Development Team.'
            );

            // Re-enable the button
            $btn.click(processRefund);
            $btn.removeClass('disabled');
        });
    };

    $actions.click(processRefund);
});
