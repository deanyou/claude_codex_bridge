from __future__ import annotations

from cc_bridge_daemon.models import CcbdShutdownReport, CcbdStartupReport
from storage.json_store import JsonStore
from storage.paths import PathLayout


class CcbdStartupReportStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> CcbdStartupReport | None:
        path = self._layout.cc_bridge_daemon_startup_report_path
        if not path.exists():
            return None
        return self._store.load(path, loader=CcbdStartupReport.from_record)

    def save(self, report: CcbdStartupReport) -> None:
        self._store.save(self._layout.cc_bridge_daemon_startup_report_path, report, serializer=lambda value: value.to_record())


class CcbdShutdownReportStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> CcbdShutdownReport | None:
        path = self._layout.cc_bridge_daemon_shutdown_report_path
        if not path.exists():
            return None
        return self._store.load(path, loader=CcbdShutdownReport.from_record)

    def save(self, report: CcbdShutdownReport) -> None:
        self._store.save(self._layout.cc_bridge_daemon_shutdown_report_path, report, serializer=lambda value: value.to_record())


__all__ = ['CcbdShutdownReportStore', 'CcbdStartupReportStore']
