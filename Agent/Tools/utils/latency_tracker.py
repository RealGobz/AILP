"""
Latency tracking utilities for LangGraph nodes and execution pipelines.
Provides thread-safe function-decorator timing, summary reporting,
and an optional LangChain BaseCallbackHandler.
"""
import time
import functools
import threading
from typing import Callable, Any, Optional
from langchain_core.callbacks import BaseCallbackHandler


class NodeLatencyTracker:
    """Thread-safe latency tracker for LangGraph nodes and pipelines."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear recorded latencies for a new turn or execution run."""
        with self._lock:
            self._records.clear()

    @property
    def records(self) -> list[dict[str, Any]]:
        """Return a copy of all recorded node execution events."""
        with self._lock:
            return [dict(r) for r in self._records]

    def track(self, name: Optional[str] = None):
        """
        Decorator to time a graph node function.
        Preserves original function signature using @functools.wraps so LangGraph
        can properly inspect and inject parameters (state, config, store, etc.).
        """
        def decorator(func: Callable):
            node_name = name or func.__name__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if self.verbose:
                    print(f"[Node Started] {node_name}...")
                start_time = time.perf_counter()
                status = "success"
                error_detail = None
                try:
                    return func(*args, **kwargs)
                except BaseException as e:
                    status = f"failed ({type(e).__name__})"
                    error_detail = str(e)
                    raise
                finally:
                    elapsed = time.perf_counter() - start_time
                    record = {
                        "node": node_name,
                        "duration_s": elapsed,
                        "duration_ms": elapsed * 1000.0,
                        "status": status,
                        "error": error_detail,
                        "timestamp": time.time(),
                    }
                    with self._lock:
                        self._records.append(record)

                    if self.verbose:
                        status_str = status.upper()
                        print(f"[Node Latency] {node_name}: {elapsed:.4f}s ({elapsed * 1000:.2f} ms) [{status_str}]")

            return wrapper
        return decorator

    def get_latencies(self) -> dict[str, float]:
        """
        Return a dictionary mapping each node name to its total latency in seconds.
        If a node executed multiple times (e.g. in loops), durations are summed.
        """
        result: dict[str, float] = {}
        with self._lock:
            for r in self._records:
                node = r["node"]
                result[node] = result.get(node, 0.0) + r["duration_s"]
        return result

    def get_node_summary(self) -> dict[str, dict[str, Any]]:
        """
        Return an aggregated summary per node including call counts, total time,
        and average time in seconds and milliseconds.
        """
        summary: dict[str, dict[str, Any]] = {}
        with self._lock:
            for r in self._records:
                node = r["node"]
                if node not in summary:
                    summary[node] = {
                        "calls": 0,
                        "total_s": 0.0,
                        "total_ms": 0.0,
                        "min_ms": float("inf"),
                        "max_ms": 0.0,
                        "status": "success",
                    }
                summary[node]["calls"] += 1
                summary[node]["total_s"] += r["duration_s"]
                summary[node]["total_ms"] += r["duration_ms"]
                summary[node]["min_ms"] = min(summary[node]["min_ms"], r["duration_ms"])
                summary[node]["max_ms"] = max(summary[node]["max_ms"], r["duration_ms"])
                if r["status"] != "success":
                    summary[node]["status"] = r["status"]

        for node, data in summary.items():
            data["avg_ms"] = data["total_ms"] / data["calls"] if data["calls"] > 0 else 0.0
            data["avg_s"] = data["total_s"] / data["calls"] if data["calls"] > 0 else 0.0

        return summary

    def print_summary(self) -> None:
        """
        Print a formatted, ASCII-safe summary table of recorded node latencies.
        Shows chronological step breakdown and total graph latency.
        """
        with self._lock:
            records = [dict(r) for r in self._records]

        if not records:
            print("\nNo node execution latency recorded.")
            return

        header = f"\n{'=' * 72}\nGRAPH NODE LATENCY SUMMARY\n{'=' * 72}"
        cols = f"{'#':<3} {'Node Name':<34} {'Latency (ms)':>14} {'Latency (s)':>12} {'Status':>7}"
        divider = "-" * 72
        print(header)
        print(cols)
        print(divider)

        total_ms = 0.0
        for idx, r in enumerate(records, start=1):
            total_ms += r["duration_ms"]
            node_name = r["node"]
            if len(node_name) > 32:
                node_name = node_name[:29] + "..."
            status_tag = "OK" if r["status"] == "success" else "FAIL"
            print(f"{idx:<3} {node_name:<34} {r['duration_ms']:>11.2f} ms {r['duration_s']:>11.4f}s {status_tag:>7}")

        print(divider)
        total_s = total_ms / 1000.0
        print(f"{'Total (sum of nodes)':<38} {total_ms:>11.2f} ms {total_s:>11.4f}s")
        print("=" * 72 + "\n")


class NodeLatencyCallback(BaseCallbackHandler):
    """
    LangChain CallbackHandler to track node latencies via LangGraph run metadata.
    Can be used by passing `config={'callbacks': [NodeLatencyCallback()]}`.
    """

    def __init__(self, verbose: bool = False):
        super().__init__()
        self.verbose = verbose
        self._starts: dict[Any, tuple[str, float]] = {}
        self.records: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        node_name = (metadata or {}).get("langgraph_node")
        if node_name:
            with self._lock:
                self._starts[run_id] = (node_name, time.perf_counter())
            if self.verbose:
                print(f"[Callback: Node Started] {node_name}...")

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            start_info = self._starts.pop(run_id, None)
        if start_info:
            node_name, start_time = start_info
            elapsed = time.perf_counter() - start_time
            record = {
                "node": node_name,
                "duration_s": elapsed,
                "duration_ms": elapsed * 1000.0,
                "status": "success",
            }
            with self._lock:
                self.records.append(record)
            if self.verbose:
                print(f"[Callback: Node Latency] {node_name}: {elapsed:.4f}s ({elapsed * 1000:.2f} ms)")

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            start_info = self._starts.pop(run_id, None)
        if start_info:
            node_name, start_time = start_info
            elapsed = time.perf_counter() - start_time
            record = {
                "node": node_name,
                "duration_s": elapsed,
                "duration_ms": elapsed * 1000.0,
                "status": f"failed ({type(error).__name__})",
            }
            with self._lock:
                self.records.append(record)
            if self.verbose:
                print(f"[Callback: Node Failed] {node_name}: {elapsed:.4f}s [{type(error).__name__}]")


# Global default tracker instance
latency_tracker = NodeLatencyTracker()
