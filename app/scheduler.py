import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .audit import AuditService
from .config import get_settings
from .intelligence_cycle import IntelligenceCycleRunner


class AutonomousCycleScheduler:
    def __init__(self, settings=None, audit_service: Optional[AuditService] = None):
        self.settings = settings or get_settings()
        self.audit_service = audit_service or AuditService(self.settings)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_run: Optional[Dict[str, Any]] = None
        self._last_error: str = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not self.settings.autonomous_scheduler_enabled:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="mne-autonomous-cycle", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.settings.autonomous_scheduler_enabled,
            "running": bool(self._thread and self._thread.is_alive()),
            "interval_seconds": self.settings.autonomous_scheduler_interval_seconds,
            "run_on_startup": self.settings.autonomous_scheduler_run_on_startup,
            "last_run": self._last_run,
            "last_error": self._last_error,
        }

    def _sleep_or_stop(self, seconds: int) -> bool:
        return self._stop_event.wait(max(seconds, 1))

    def _execute_cycle(self) -> None:
        runner = IntelligenceCycleRunner(self.settings, self.audit_service)
        trigger_context = {
            "source": "scheduler",
            "event_timestamp": datetime.utcnow().isoformat() + "Z",
        }
        result = runner.run(
            mode="scheduled",
            trigger_context=trigger_context,
            force_report=self.settings.autonomous_always_send_report,
        )
        self._last_run = {
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "decision_summary": result.get("decision", {}).get("summary"),
            "completed_at": datetime.utcnow().isoformat() + "Z",
        }
        self._last_error = ""

    def _run_loop(self) -> None:
        if self.settings.autonomous_scheduler_run_on_startup:
            self._run_once_with_error_capture()

        while not self._sleep_or_stop(self.settings.autonomous_scheduler_interval_seconds):
            self._run_once_with_error_capture()

    def _run_once_with_error_capture(self) -> None:
        try:
            self._execute_cycle()
        except Exception as exc:
            self._last_error = str(exc)
            self.audit_service.log_agent_run(
                mode="scheduled",
                status="failed",
                trigger_source="scheduler",
                trigger_context={
                    "source": "scheduler",
                    "event_timestamp": datetime.utcnow().isoformat() + "Z",
                },
                error_message=str(exc),
            )
