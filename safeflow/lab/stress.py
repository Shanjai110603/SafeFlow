"""High-Throughput Concurrency & Stress Testing Harness for SafeFlow.

Simulates thousands of concurrent decision evaluations and profile image gating
operations to benchmark sub-millisecond latencies and P99 throughput.
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any
import numpy as np

from safeflow.core.decision.engine import DecisionEngine
from safeflow.core.schema import Signal


class SafeFlowStressTester:
    """Benchmark engine measuring concurrency, latency percentiles, and throughput."""

    @classmethod
    def run_decision_engine_benchmark(
        cls,
        concurrency: int = 20,
        total_requests: int = 1000,
        actor_id_prefix: str = "stress_actor",
    ) -> dict[str, Any]:
        """Stress test the decision engine with simulated multi-modal signal evaluations."""
        engine = DecisionEngine()

        # Pre-synthesize synthetic signal payloads
        test_payloads = [
            [
                Signal(subject_type="actor", subject_id="a", family="PROFILE_CHANGE", name="bio_callout", value=0.85, producer="p", producer_version="1.0.0"),
                Signal(subject_type="actor", subject_id="a", family="DESTINATION", name="max_risk", value=0.90, producer="d", producer_version="1.0.0"),
                Signal(subject_type="actor", subject_id="a", family="TARGETING", name="popular_conc", value=0.80, producer="t", producer_version="1.0.0"),
            ],
            [
                Signal(subject_type="actor", subject_id="b", family="BEHAVIOR", name="text_rep", value=0.1, producer="b", producer_version="1.0.0"),
            ],
            [
                Signal(subject_type="actor", subject_id="c", family="IMAGE_LINK", name="media_reuse_count", value=5.0, producer="i", producer_version="1.0.0"),
                Signal(subject_type="actor", subject_id="c", family="BEHAVIOR", name="text_rep", value=0.85, producer="b", producer_version="1.0.0"),
                Signal(subject_type="actor", subject_id="c", family="TARGETING", name="popular_conc", value=0.95, producer="t", producer_version="1.0.0"),
                Signal(subject_type="actor", subject_id="c", family="DESTINATION", name="max_risk", value=0.99, producer="d", producer_version="1.0.0"),
            ],
        ]

        latencies_ms: list[float] = []

        def worker_task(idx: int) -> float:
            sig_list = test_payloads[idx % len(test_payloads)]
            t0 = time.perf_counter()
            engine.evaluate_actor(actor_id=f"{actor_id_prefix}_{idx}", signals=sig_list)
            t1 = time.perf_counter()
            return (t1 - t0) * 1000.0  # ms

        start_time = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker_task, i) for i in range(total_requests)]
            for fut in concurrent.futures.as_completed(futures):
                latencies_ms.append(fut.result())
        total_duration = time.perf_counter() - start_time

        latencies_arr = np.array(latencies_ms)
        rps = total_requests / total_duration if total_duration > 0 else 0.0

        return {
            "total_requests": total_requests,
            "concurrency": concurrency,
            "total_duration_sec": round(total_duration, 4),
            "throughput_rps": round(rps, 2),
            "latency_p50_ms": round(float(np.percentile(latencies_arr, 50)), 3),
            "latency_p90_ms": round(float(np.percentile(latencies_arr, 90)), 3),
            "latency_p95_ms": round(float(np.percentile(latencies_arr, 95)), 3),
            "latency_p99_ms": round(float(np.percentile(latencies_arr, 99)), 3),
            "latency_mean_ms": round(float(np.mean(latencies_arr)), 3),
            "latency_max_ms": round(float(np.max(latencies_arr)), 3),
        }
