6. Add fallback for ecommerce sdn check
------------------------------------------------------------

Status
------

Accepted (August 2020)

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

2. **Storing the data**

When activating the fallback one consideration was whether we would retrieve and process the CSV during the lifecycle of the request or do so ahead of time and store the data. The decision was to process the CSV in an automated job and store the data. 
One reason is that the fallback wouldn't work reliably if the CSV has periods of downtime like the API. With this approach we would use a request cache, but if the cache expired during downtime of the CSV then the fallback wouldn't have any data available. By storing the data there will always be a somewhat recent set of data to check the transaction against.
A second reason is that by having the processed data stored in a database, debugging of any production issues with the related code should be simpler.
This approach would have a more expensive engineering implementation cost, but we are willing to make that trade off.

3. **Allowing transactions**

If we are unable to check a transaction against the list we currently allow the transaction to succeed. The hope is that with the fallback in place, fewer transactions will fall through without being checked, and therefore allowing them will be less of a liability.

4. **Algorithm**

For the algorithm in the fallback to match name/address pairs to entries in the list we chose to attempt to replicate the algorithm used by the API as much as possible. Although we don't know what the exact algorithm is, we used some test queries to identify key properties of the algorithm and will implement the simplest algorithm that retains the same properties.

5. **Location of the code**

We will implement the fallback in ecommerce because the primary SDN check is in ecommerce so it will live close to existing relevant code.

Consequences
------------

When the `ConsolidatedScreeningListAPI` goes down, we will have a fallback option available to call.