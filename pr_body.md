💡 What: Batch insert requests in `services/scheduler.py` (`_generate_requests`).

🎯 Why: The original implementation used `db.pool.execute` inside a loop, which caused an N+1 queries performance bottleneck.

📊 Impact: Reduces database round-trips from N (number of stations generated for the request) to 1. Expected improvement in CPU utilization on the database and lower connection time.

🔬 Measurement: Review changes in database query throughput/latency metrics or by checking the time execution difference using `time`.
