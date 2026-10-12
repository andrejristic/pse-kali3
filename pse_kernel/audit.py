# =============================================================================
# PSE-KALI — AUDIT LOG (one shared append-only JSONL)
# SR&ED evidence from day 1, and the pentest engagement record. Thread-safe:
# all three concurrent units write to the same log through one lock.
# =============================================================================
import json
import os
import threading
import time


class AuditLog:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def append(self, record):
        record = dict(record)
        record.setdefault("ts", time.time())
        line = json.dumps(record, default=str)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return record


class NullAudit:
    """For tests / dry runs: records in memory, writes nothing to disk."""
    def __init__(self):
        self.records = []
        self._lock = threading.Lock()

    def append(self, record):
        record = dict(record)
        record.setdefault("ts", time.time())
        with self._lock:
            self.records.append(record)
        return record
