import os
import time
from contextlib import contextmanager

class ConcurrencyManager:
    """
    Manages concurrency for state-changing operations (Commands).
    Uses a simple file-based lock mechanism until Redis is introduced.
    Enforces FAIL-FAST policy: If lock is held, immediately raise error.
    """
    def __init__(self, lock_dir: str = ".locks"):
        self.lock_dir = lock_dir
        os.makedirs(self.lock_dir, exist_ok=True)

    @contextmanager
    def acquire_lock(self, resource_id: str):
        lock_file = os.path.join(self.lock_dir, f"{resource_id}.lock")
        
        if os.path.exists(lock_file):
            # Check for stale lock (older than 60 seconds)
            if time.time() - os.path.getmtime(lock_file) > 60:
                os.remove(lock_file) # Remove stale lock
            else:
                # FAIL-FAST: Immediately raise error if locked
                raise BlockingIOError(f"Resource {resource_id} is currently locked by another process.")

        try:
            with open(lock_file, 'w') as f:
                f.write(str(time.time()))
            yield
        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)
