$(document).ready(function () {
    var retryFulfillment = function (e) {
        var $btn = $(e.target),
            order_number = $btn.data('order-number'),
            message = '';

        // Disable button
        e.preventDefault();
        $btn.addClass('disabled');
        $btn.unbind("click");

        // Make AJAX call and update status
        $.ajax({
            url: '/api/v2/orders/' + order_number + '/fulfill/',
            method: 'PUT',
            headers: {'X-CSRFToken': Cookies.get('ecommerce_csrftoken')}
        }).done(function (data) {
            $('tr[data-order-number=' + order_number + '] .order-status').text(data.status);

            message = interpolate(
                gettext('Order %(order_number)s has been fulfilled.'), {order_number: order_number}, true
            );
            addMessage('alert-success', 'icon-check-sign', message);
            $btn.remove();
        }).fail(function (jqXHR, textStatus, errorThrown) {
            message = interpolate(
                gettext('Failed to fulfill order %(order_number)s: %(error)s'),
                {order_number: order_number, error: errorThrown},
                true
            );
            addMessage('alert-error', 'icon-exclamation-sign', message);

            // Re-enable the button
            $btn.click(retryFulfillment);
            $btn.removeClass('disabled');
        });
    };

    $('[data-action=retry-fulfillment]').click(retryFulfillment);
});
