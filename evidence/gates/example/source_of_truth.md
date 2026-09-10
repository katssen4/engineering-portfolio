# Meridian

**Ingestion pipeline for time series**

## Summary

Meridian ingests sensor readings and writes them to a column store. It has been running on one
site since March 2026.

## Measured

- Sustained throughput of 48000 events per second on a single node, measured over 6 hours.
- Median write latency of 4 milliseconds, 99th percentile at 21 milliseconds.
- The store holds 312 million rows across 4 tables.
- 87 unit tests and 12 integration tests, all passing on the pinned dependency set.

## Not measured

- Behaviour beyond one node. There is no cluster, so nothing about scaling is known.
- Recovery time after a disk failure. The procedure is written but has never been executed.
