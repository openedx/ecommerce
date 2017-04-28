require([
        'routers/program_router',
        'utils/navigate'
    ],
    function (ProgramRouter,
              navigate) {
        'use strict';

        $(function () {
            var $app = $('#app'),
                programApp = new ProgramRouter({$el: $app});

            programApp.start();

            // Handle navbar clicks.
            $('a.navbar-brand').on('click', navigate);

            // Handle internal clicks
            $app.on('click', 'a', navigate);
        });
    }
);
