function addMessage(type, icon, msg) {
    var html = '<div class="alert ' + type + '">\
            <a class="close" data-dismiss="alert" href="#">×</a>\
            <div class="alertinner wicon"><span class="message">' + msg + '</span><i class="' + icon + '"></i></div></div>';

    $('#messages').append(html).hide().fadeIn(500);
}
