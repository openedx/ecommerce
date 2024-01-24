"""
Variation on the "promise" design pattern.
Promises make it easier to handle asynchronous operations correctly.
"""

import logging
import time

LOGGER = logging.getLogger(__name__)


class BrokenPromise(Exception):
    """
    The promise was not satisfied within the time constraints.
    """

    def __init__(self, promise):
        """
        Configure the broken promise error.

        Args:
            promise (Promise): The promise that was not satisfied.
        """
        super().__init__()
        self._promise = promise

    def __str__(self):
        return f"Promise not satisfied: {self._promise}"


class Promise:
    """
    Check that an asynchronous action completed, blocking until it does
    or timeout / try limits are reached.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, check_func, description, try_limit=None, try_interval=0.5, timeout=30):
        """
        Configure the `Promise`.

        The `Promise` will poll `check_func()` until either:
            * The promise is satisfied
            * The promise runs out of tries (checks more than `try_limit` times)
            * The promise runs out of time (takes longer than `timeout` seconds)

        If the try_limit or timeout is reached without success, then the promise is "broken" and
        an exception will be raised.

        Note that if you specify a try_limit but not a timeout, the default timeout is still used.
        This is to prevent an inadvertent infinite loop. If you want to make sure that the
        try_limit expires first (and thus that many attempts will be made), then you should also
        pass in a larger value for timeout.

        `description` is a string that will be included in the exception to make debugging easier.

        Example:

        .. code:: python

            # Dummy check function that indicates the promise is always satisfied
            check_func = lambda: (True, "Hello world!")

            # Check up to 5 times if the operation has completed
            result = Promise(check_func, "Operation has completed", try_limit=5).fulfill()

        Args:
            check_func (callable): A function that accepts no arguments and returns a `(is_satisfied, result)` tuple,
                where `is_satisfied` is a boolean indiating whether the promise was satisfied, and `result`
                is a value to return from the fulfilled `Promise`.

            description (str): Description of the `Promise`, used in log messages.

        Keyword Args:
            try_limit (int or None): Number of attempts to make to satisfy the `Promise`.
                Can be `None` to disable the limit.
            try_interval (float): Number of seconds to wait between attempts.
            timeout (float): Maximum number of seconds to wait for the `Promise` to be satisfied before timing out.

        Returns:
            Promise
        """
        self._check_func = check_func
        self._description = description
        self._try_limit = try_limit
        self._try_interval = try_interval
        self._timeout = timeout
        self._num_tries = 0

    def fulfill(self):
        """
        Evaluate the promise and return the result.

        Returns:
             The result of the `Promise` (second return value from the `check_func`)

        Raises:
            BrokenPromise: the `Promise` was not satisfied within the time or attempt limits.
        """
        is_fulfilled, result = self._check_fulfilled()

        if is_fulfilled:
            return result
        raise BrokenPromise(self)

    def __str__(self):
        return str(self._description)

    def _check_fulfilled(self):
        """
        Return tuple `(is_fulfilled, result)` where
        `is_fulfilled` is a boolean indicating whether the promise has been fulfilled
        and `result` is the value to pass to the `with` block.
        """
        is_fulfilled = False
        result = None
        start_time = time.time()

        # Check whether the promise has been fulfilled until we run out of time or attempts
        while self._has_time_left(start_time) and self._has_more_tries():

            # Keep track of how many attempts we've made so far
            self._num_tries += 1

            is_fulfilled, result = self._check_func()

            # If the promise is satisfied, then continue execution
            if is_fulfilled:
                break

            # Delay between checks
            time.sleep(self._try_interval)

        return is_fulfilled, result

    def _has_time_left(self, start_time):
        """
        Return True if the elapsed time is less than the timeout.
        """
        return time.time() - start_time < self._timeout

    def _has_more_tries(self):
        """
        Return True if the promise has additional tries.
        If `_try_limit` is `None`, always return True.
        """
        if self._try_limit is None:
            return True
        return self._num_tries < self._try_limit


class EmptyPromise(Promise):  # pylint: disable=too-few-public-methods
    """
    A promise that has no result value.
    """

    def __init__(self, check_func, description, **kwargs):
        """
        Configure the promise.

        Unlike a regular `Promise`, the `check_func()` does NOT return a tuple
        with a result value.  That's why the promise is "empty" -- you don't get anything back.

        Example usage:

        .. code:: python

            # This will block until `is_done` returns `True` or we reach the timeout limit.
            EmptyPromise(lambda: is_done('test'), "Test operation is done").fulfill()

        Args:
            check_func (callable): Function that accepts no arguments and
                returns a boolean indicating whether the promise is fulfilled.
            description (str): Description of the Promise, used in log messages.

        Returns:
            EmptyPromise
        """
        def full_check_func():
            check_result = check_func()
            return check_result, None

        super().__init__(full_check_func, description, **kwargs)
