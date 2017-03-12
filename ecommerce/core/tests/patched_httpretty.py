# Note (CCB): We must patch httpretty to work around SSL issues.
# See https://github.com/gabrielfalcao/HTTPretty/issues/242, and remove this once an proper fix is in place.

import httpretty
import httpretty.core
from httpretty import HTTPretty as OriginalHTTPretty

try:
    from requests.packages.urllib3.contrib.pyopenssl import inject_into_urllib3, extract_from_urllib3

    pyopenssl_override = True
except:  # pylint: disable=bare-except
    pyopenssl_override = False


class PatchedHTTPretty(httpretty.HTTPretty):
    """ pyopenssl monkey-patches the default ssl_wrap_socket() function in the 'requests' library,
    but this can stop the HTTPretty socket monkey-patching from working for HTTPS requests.

    Our version extends the base HTTPretty enable() and disable() implementations to undo
    and redo the pyopenssl monkey-patching, respectively.
    """

    @classmethod
    def enable(cls):
        OriginalHTTPretty.enable()
        if pyopenssl_override:
            # Take out the pyopenssl version - use the default implementation
            extract_from_urllib3()

    @classmethod
    def disable(cls):
        OriginalHTTPretty.disable()
        if pyopenssl_override:
            # Put the pyopenssl version back in place
            inject_into_urllib3()


httpretty.core.httpretty = PatchedHTTPretty
httpretty.httpretty = PatchedHTTPretty
