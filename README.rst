This branch demonstrates the Karma failure logged at https://github.com/karma-runner/karma/issues/2675.

Run the following steps to recreate the failure:

   .. code-block:: bash

    npm install
    make validate_js


My output resembles:

   .. code-block:: text

    maCCB-MacBook-Pro:ecommerce clintonb$ make validate_js
    rm -rf coverage
    ./node_modules/.bin/gulp test
    [19:00:31] Using gulpfile ~/workspace/ecommerce/gulpfile.js
    [19:00:31] Starting 'test'...
    03 05 2017 19:00:31.922:WARN [watcher]: Pattern "/Users/clintonb/workspace/ecommerce/ecommerce/static/vendor/**/*.js" does not match any file.
    03 05 2017 19:00:32.094:WARN [watcher]: All files matched by "/Users/clintonb/workspace/ecommerce/ecommerce/static/js/config.js" were excluded or matched by prior matchers.
    03 05 2017 19:00:32.095:WARN [watcher]: All files matched by "/Users/clintonb/workspace/ecommerce/ecommerce/static/js/test/spec-runner.js" were excluded or matched by prior matchers.
    03 05 2017 19:00:32.573:INFO [karma]: Karma v1.6.0 server started at http://0.0.0.0:9876/
    03 05 2017 19:00:32.573:INFO [launcher]: Launching browser Firefox with unlimited concurrency
    03 05 2017 19:00:32.582:INFO [launcher]: Starting browser Firefox
    03 05 2017 19:00:34.490:INFO [Firefox 53.0.0 (Mac OS X 10.12.0)]: Connected on socket IBIdKiF8Vkwac0ruAAAA with id 14472089
    03 05 2017 19:00:44.498:WARN [Firefox 53.0.0 (Mac OS X 10.12.0)]: Disconnected (1 times), because no message in 10000 ms.
    Firefox 53.0.0 (Mac OS X 10.12.0) ERROR
      Disconnected, because no message in 10000 ms.

    Firefox 53.0.0 (Mac OS X 10.12.0): Executed 0 of 0 DISCONNECTED (10.009 secs / 0 secs)

    [19:00:44] 'test' errored after 13 s
    [19:00:44] Error: 1
        at formatError (/Users/clintonb/workspace/ecommerce/node_modules/gulp/bin/gulp.js:169:10)
        at Gulp.<anonymous> (/Users/clintonb/workspace/ecommerce/node_modules/gulp/bin/gulp.js:195:15)
        at emitOne (events.js:96:13)
        at Gulp.emit (events.js:188:7)
        at Gulp.Orchestrator._emitTaskDone (/Users/clintonb/workspace/ecommerce/node_modules/orchestrator/index.js:264:8)
        at /Users/clintonb/workspace/ecommerce/node_modules/orchestrator/index.js:275:23
        at finish (/Users/clintonb/workspace/ecommerce/node_modules/orchestrator/lib/runTask.js:21:8)
        at cb (/Users/clintonb/workspace/ecommerce/node_modules/orchestrator/lib/runTask.js:29:3)
        at removeAllListeners (/Users/clintonb/workspace/ecommerce/node_modules/karma/lib/server.js:380:7)
        at Server.<anonymous> (/Users/clintonb/workspace/ecommerce/node_modules/karma/lib/server.js:391:9)
        at Server.g (events.js:292:16)
        at emitNone (events.js:91:20)
        at Server.emit (events.js:185:7)
        at emitCloseNT (net.js:1544:8)
        at _combinedTickCallback (internal/process/next_tick.js:71:11)
        at process._tickCallback (internal/process/next_tick.js:98:9)
    make: *** [validate_js] Error 1

