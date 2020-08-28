6. Add fallback for ecommerce sdn check
------------------------------------------------------------

Status
------

Accepted (September 2020)

Context
-------

When learners attempt to place an order in ecommerce through our Cybersource flow, edX makes a call to the `ConsolidatedScreeningListAPI` at `trade.gov` to check that we are legally allowed to process the transaction for that learner.
The API has periods of downtime and although that downtime is often within the 99.5% uptime SLA of the service, edX would prefer to take extra precautions when downtime occurs to reduce our legal liability.
For this reason, we are developing a fallback that we can call when the API is down.

Decision
--------

`trade.gov` also provides a CSV alternative to the API, so we will leverage that option for the fallback by processing the CSV and storing the data which we'll be able to call as needed.

1. **Using the CSV as a fallback vs as a primary solution**

We are only going to use the CSV when the API is down, not replace the API calls with the CSV. The reason is that the API is up the vast majority of the time and during that time we know the data is the most up to date, so the CSV makes more sense as a fallback rather than primary solution.

1a. **Selection of which worker will run the task to download the CSV**

As per OEP-0003, we generally use celery to run asynchronous tasks, with some scheduler (Jenkins, Kubernetes) if task runs periodically. 
Ecommerce is an exception/antipattern to this general approach; it doesn't use Celery directly. Instead, we have a separate service called ecommerce-worker that has a Celery integration. 
Ecommerce-worker doesn't have access to the ecommerce database, so any database interaction with ecommerce needs to happen on the main ecommerce server machine. 

Our workaround for cases like this is to do the work on a Jenkins machine (so Jenkins is both the scheduler and the worker). The download task is fairly lightweight, and impact is small if a run failed to complete. 

2. **Storing the data**

When activating the fallback one consideration was whether we would retrieve and process the CSV during the lifecycle of the request or do so ahead of time and store the data. The decision was to process the CSV in an automated job and store the data. 
One reason is that the fallback wouldn't work reliably if the CSV has periods of downtime like the API. With this approach we would use a request cache, but if the cache expired during downtime of the CSV then the fallback wouldn't have any data available. By storing the data there will always be a somewhat recent set of data to check the transaction against.
A second reason is that by having the processed data stored in a database, debugging of any production issues with the related code should be simpler.
This approach would have a more expensive engineering implementation cost, but we are willing to make that trade off.

3. **Denormalizing the data*

One option is to denormalize the data, where each row would be a unique combination of person, country, and type. The benefit would be having better performance in the query to filter the data, for example when filtering by country. However, more space would be used in the database since one record could have multiple rows.
The second option would be to keep the data normalized, where we would have one row in the database per record in the CSV. This would more closely match the API and more closely match the data from the imported CSV. The database would also require less space.
We decided to go with keeping the data normalized because the performance gains of denormalizing would not be substantial enough to outweigh the costs to complexity and space.

4. **Allowing transactions**

If we are unable to check a transaction against the list we currently allow the transaction to succeed. The hope is that with the fallback in place, fewer transactions will fall through without being checked, and therefore allowing them will be less of a liability.

5. **Algorithm**

For the algorithm in the fallback to match name/address pairs to entries in the list we chose to attempt to replicate the algorithm used by the API as much as possible. Although we don't know what the exact algorithm is, we used some test queries to identify key properties of the algorithm and will implement the simplest algorithm that retains the same properties.

6. **Location of the code**

We will implement the fallback in ecommerce because the primary SDN check is in ecommerce so it will live close to existing relevant code.

Consequences
------------

When the `ConsolidatedScreeningListAPI` goes down, we will have a fallback option available to call.