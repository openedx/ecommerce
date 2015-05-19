$(document).ready(function () {
    var retryFulfillment = function (e) {
        var $btn = $(e.target),
            order_number = $btn.data('order-number');

        // Disable button
        e.preventDefault();
        $btn.addClass('disabled');
        $btn.unbind("click");

        // Make AJAX call and update status
        $.ajax({
            url: '/api/v2/orders/' + order_number + '/fulfill/',
            method: 'PUT',
            headers: {'X-CSRFToken': $.cookie('csrftoken')}
        }).success(function (data) {
            $('tr[data-order-number=' + order_number + '] .order-status').text(data.status);
            addMessage('alert-success', 'icon-check-sign', 'Order ' + order_number + ' has been fulfilled.');
            $btn.remove();
        }).fail(function (jqXHR, textStatus, errorThrown) {
            addMessage('alert-error', 'icon-exclamation-sign', 'Failed to fulfill order ' + order_number + ': ' + errorThrown);

            // Re-enable the button
            $btn.click(retryFulfillment);
            $btn.removeClass('disabled');
        });
    };

    $('[data-action=retry-fulfillment]').click(retryFulfillment);
});
