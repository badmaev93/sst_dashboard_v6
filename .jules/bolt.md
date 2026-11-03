## 2024-05-18 - Batch Database Inserts to Avoid N+1 Problem
**Learning:** In asynchronous loops in Python where database interactions are done repeatedly (`await db.pool.execute` inside a loop), this causes an N+1 queries performance bottleneck which is highly inefficient for large iterations.
**Action:** Always batch these database actions utilizing `await db.pool.executemany` which compiles operations into a single execute to improve application performance when processing bulk changes (like metrics ingest from sensors).

## $(date +%Y-%m-%d) - Use asyncio.gather for independent db queries
**Learning:** Using sequential `await` statements for independent database reads (e.g. `await db.pool.fetch...`) causes N+1 query execution bottlenecks, where each query awaits the completion of the previous one before starting.
**Action:** When multiple independent queries are required to build a single response object or process data, group them into an `asyncio.gather` call so they can execute concurrently, thus reducing total endpoint latency.
