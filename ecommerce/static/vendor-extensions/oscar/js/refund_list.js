$(document).ready(function () {

    var processRefund = function (e) {
        var $btn = $(e.target),
            refund_id = $btn.data('refund-id'),
            decision = $btn.data('decision'),
            message = '';

        // Disable button
        e.preventDefault();
        $btn.addClass('disabled');
        $btn.unbind('click');

        // Make AJAX call and update status
        $.ajax({
            url: '/api/v2/refunds/' + refund_id + '/process/',
            data: { action: decision },
            method: 'PUT',
            headers: {'X-CSRFToken': Cookies.get('ecommerce_csrftoken')}
        }).success(function (data) {
            $('tr[data-refund-id=' + refund_id + '] .refund-status').text(data.status);

            message = interpolate(
                gettext('Refund #%(refund_id)s has been processed.'), {refund_id: refund_id}, true
            );
            addMessage('alert-success', 'icon-check-sign', message);
            $('tr[data-refund-id=' + refund_id + '] [data-action=process-refund]').remove();
        }).fail(function (jqXHR, textStatus, errorThrown) {
            // NOTE (RFL): For an MVP, changing the displayed refund state on any error may be viable.
            // Ideally, the displayed refund state would only change if the refund were to enter an
            // error state. This would be easiest if the processing endpoint returned 200 and a serialized
            // refund, even when the refund has entered an error state during processing.
            $('tr[data-refund-id=' + refund_id + '] .refund-status').text(gettext('Error'));

            message = interpolate(
                gettext('Failed to process refund #%(refund_id)s: %(error)s. Please try again, or contact the E-Commerce Development Team.'),
                {refund_id: refund_id, error: errorThrown},
                true
            );
            addMessage(
                'alert-error',
                'icon-exclamation-sign',
                message
            );
        }).always(function () {
            // Re-enable the button
            $btn.click(processRefund);
            $btn.removeClass('disabled');
        });

        // dismiss the modal
        $('#refundActionModal').modal( 'hide' );
    };

    var launchRefundActionModal = function (e) {
        var $button = $( e.target ),
            refundId = $button.data( 'refundId' ),
            decision = $button.data( 'decision'),
            $modal = $('#refundActionModal');

        // the message varies depending on the decision; hide both messages, and then
        // reveal the one appropriate to the selected decision.
        $modal.find( '.modal-body' ).hide();
        $modal.find( '.modal-body.confirm-' + decision ).show();
        // set the decision and refund id on the modal's confirm button.
        $modal.find( '.btn-primary' ).data( 'refundId', refundId ).data( 'decision', decision );
        $modal.modal( 'show' );
    };

    // bind clicks on refund action buttons to the modal.
    $( '[data-action=process-refund]' ).click( launchRefundActionModal );
    // bind modal confirmation clicks to the refund processing ajax call.
    $( '#refundActionModal .btn-primary' ).click( processRefund );

});
