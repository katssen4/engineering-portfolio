# Meridian

**Time series ingestion**

## Summary

Meridian ingests sensor readings and writes them to a column store, running on one site since
March 2026.

## Measured

- Sustained throughput of 48000 events per second on a single node, measured over 6 hours.
- Median write latency of 4 milliseconds.
- 87 unit tests, all passing on the pinned dependency set.

## Not measured

- Behaviour beyond one node. There is no cluster, so nothing about scaling is known.
