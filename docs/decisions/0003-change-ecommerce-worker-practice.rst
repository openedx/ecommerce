3. Follow practice of other workers for ecommerce-worker
--------------------------------------------------------

Status
------

Draft

Context
-------

The ecommerce-workers are currently deployed using a separate codebase in the edx/ecommerce-worker repository.
Additionally, the ecommerce-worker tasks make callbacks to the ecommerce service, where the work is actually
performed.

This is different from other workers, like those used for LMS.  In the LMS, the workers get the same edx-platform
codebase and the workers complete the tasks, sometimes long-running, in their own processes.

The current setup of the ecommerce-workers was an attempt at a new pattern to help with some potential deployment
issues that are not well understood at this time, and don't seem to be a strong issue in the LMS worker pattern.
Additionally, the current setup has the following issues:

* It is more difficult to share code between the ecommerce service and the ecommerce workers, given it isn't a
  single codebase.

* Long running tasks are run on the ecommerce service, which is serving end-users, and unnecessarily competing for
  resources.

Decision
--------

There is no compelling reason to keep the current setup for ecommerce workers, and there would be benefits to
switching to the LMS worker model, where: 1) a shared codebase is used for both the service and the workers, and
2) tasks are run in the context of the workers.  This decision is to pave the way for that switch when and if
there is a change that would benefit enough to invest in this change.

When and if the switch to the LMS model for workers happens, this ADR should be updated or superseded appropriately.

Consequences
------------

Given that we are not yet updating the ecommerce worker model, at this time the only consequence of this decision is
that the team should now feel free to update the model as described above at the earliest convenience.

This will ultimately result in the following benefits:

* Ease of sharing code between the ecommerce service and ecommerce workers.

* Offloading processing from the ecommerce service to the ecommerce workers, to relieve the service from this load
  so it can concentrate on responding to end-users.
