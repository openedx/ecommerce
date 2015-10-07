Asset Pipeline
==============

Static files are managed via `django-compressor`_. `RequireJS`_ and r.js are used to manage JavaScript dependencies.
django-compressor compiles SASS, minifies JavaScript, and handles naming files to facilitate cache busting during deployment.

.. _django-compressor: http://django-compressor.readthedocs.org/
.. _RequireJS: http://requirejs.org/

Both tools should operate seamlessly in a local development environment. When deploying to production, call
``make static`` to compile all static assets and move them to the proper location to be served.

When creating new pages that utilize RequireJS dependencies, remember new modules to ``build.js``.

NOTE 1: django-compressor uses `Closure Compiler <https://developers.google.com/closure/compiler/>`_ to minify assets.
Closure Compiler requires `JDK 7+ <http://openjdk.java.net/>`_ to be installed on your system, and the ``java``
command available on your ``PATH``.

NOTE 2: The static file directories are setup such that the build output directory of ``r.js`` is read before checking
for assets in ``ecommerce\static\``. If you run ``make static`` or ``r.js`` locally (which you should not need to),
make sure you delete ``ecommerce/static/build`` or run ``make static`` before continuing with development. If you do not
all changes made to static files will be ignored.
