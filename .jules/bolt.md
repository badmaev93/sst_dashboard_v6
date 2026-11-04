## 2024-05-18 - Batch Database Inserts to Avoid N+1 Problem
**Learning:** In asynchronous loops in Python where database interactions are done repeatedly (`await db.pool.execute` inside a loop), this causes an N+1 queries performance bottleneck which is highly inefficient for large iterations.
**Action:** Always batch these database actions utilizing `await db.pool.executemany` which compiles operations into a single execute to improve application performance when processing bulk changes (like metrics ingest from sensors).

## 2025-02-04 - Batch Independent Database Queries with asyncio.gather
**Learning:** When a single endpoint executes multiple independent asynchronous database queries sequentially, it creates an unnecessary latency bottleneck that scales linearly with the number of queries.
**Action:** Refactor sequential database read queries (e.g. using `await db.pool.fetch...`) into a single `asyncio.gather(...)` block to execute them concurrently, significantly reducing response latency.
