\
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .connectors import TelegramConnector, EmailConnector
from .repository import utc_now

LOG = logging.getLogger("seiden_flow.era")


def _duration_text(opened_at: str | None, recovered_at: str | None = None) -> str:
    try:
        start = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(recovered_at).replace("Z", "+00:00")) if recovered_at else datetime.now(timezone.utc)
        seconds = max(0, int((end - start).total_seconds()))
        if seconds < 60:
            return f"{seconds} s"
        if seconds < 3600:
            return f"{seconds // 60} min"
        h, m = divmod(seconds // 60, 60)
        return f"{h} h {m:02d} min"
    except Exception:
        return "—"


class ERAService:
    def __init__(self, repo, settings, fleet_client=None):
        self.repo = repo
        self.settings = settings
        self.fleet_client = fleet_client
        self.stop_event = threading.Event()
        self.thread = None
        self.telegram = TelegramConnector(
            settings.era_telegram_enabled,
            settings.era_telegram_bot_token,
            settings.era_telegram_default_chat_id,
            settings.era_telegram_routes,
        )
        self.email = EmailConnector(
            settings.era_email_enabled,
            settings.era_email_smtp_host,
            settings.era_email_smtp_port,
            settings.era_email_username,
            settings.era_email_password,
            settings.era_email_from,
            settings.era_email_to,
            settings.era_email_starttls,
        )

    @property
    def configured_channels(self):
        return {
            "telegram": {"enabled": self.telegram.enabled, "configured": self.telegram.configured},
            "email": {"enabled": self.email.enabled, "configured": self.email.configured},
        }

    def start(self):
        if not self.settings.era_enabled or (self.thread and self.thread.is_alive()):
            return
        self.thread = threading.Thread(target=self._run, name="seiden-era", daemon=True)
        self.thread.start()
        LOG.info("ERA 0.1.0 iniciada | poll=%ss | telegram=%s | email=%s",
                 self.settings.era_poll_seconds, self.telegram.configured, self.email.configured)

    def _run(self):
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.sync_ita()
            except Exception:
                LOG.exception("ERA: falha ao sincronizar ITA")
            try:
                self.dispatch()
            except Exception:
                LOG.exception("ERA: falha no dispatcher")
            wait = max(5, int(self.settings.era_poll_seconds) - int(time.monotonic() - started))
            self.stop_event.wait(wait)

    def ingest(self, event: dict[str, Any]):
        result = self.repo.apply_event(
            event,
            critical_delay=self.settings.era_critical_delay_minutes,
            warning_delay=self.settings.era_warning_delay_minutes,
        )
        self.dispatch()
        return result

    def _ita_event(self, asset, key, title, severity, state, details=None):
        return {
            "source_module": "ITA",
            "tenant_id": asset.get("tenant_id") or "default",
            "asset_id": asset.get("pulse_id") or asset.get("system_id") or "unknown",
            "asset_name": asset.get("asset_name") or asset.get("pulse_id") or "Ativo",
            "event_key": key,
            "event_type": "infrastructure.alert",
            "severity": severity,
            "state": state,
            "title": title,
            "timestamp": utc_now(),
            "details": details or {},
        }

    def sync_ita(self):
        if not self.fleet_client or not self.fleet_client.configured:
            return
        fleet = self.fleet_client.fleet("active")
        assets = fleet.get("assets") or []
        stale_after_s = max(60, int(self.settings.era_telemetry_stale_minutes) * 60)

        for asset in assets:
            tenant = asset.get("tenant_id") or "default"
            asset_id = asset.get("pulse_id") or ""
            if not asset_id:
                continue

            # Server-side silence detection: the agent does not need to say it died.
            age = asset.get("last_seen_age_seconds")
            stale = age is None or float(age) >= stale_after_s
            self.ingest(self._ita_event(
                asset,
                "telemetry.stale",
                "Sem telemetria",
                "critical",
                "active" if stale else "recovered",
                {"last_seen_age_seconds": age, "threshold_seconds": stale_after_s},
            ))

            current_alert_keys = set()
            if int(asset.get("active_alerts") or 0) > 0:
                detail = self.fleet_client.asset(asset_id)
                for alert in detail.get("alerts") or []:
                    alert_key = str(alert.get("alert_key") or alert.get("key") or "").strip()
                    if not alert_key:
                        continue
                    source_key = f"alert:{alert_key}"
                    current_alert_keys.add(source_key)
                    severity = str(alert.get("severity") or "warning").lower()
                    if severity not in ("critical", "warning"):
                        severity = "warning"
                    self.ingest(self._ita_event(
                        asset,
                        source_key,
                        alert.get("title") or alert_key,
                        severity,
                        "active",
                        alert.get("details") or {},
                    ))

            # Recover ITA alerts that were previously open but no longer exist in Receiver active_alerts.
            for incident in self.repo.open_for_asset("ITA", tenant, asset_id):
                key = incident.get("source_event_key") or ""
                if key.startswith("alert:") and key not in current_alert_keys:
                    self.ingest(self._ita_event(
                        asset, key, incident.get("title") or key,
                        incident.get("severity") or "warning", "recovered", incident.get("details") or {}
                    ))

    def _message(self, incident, phase: str):
        critical = incident.get("severity") == "critical"
        if phase == "open":
            icon = "🔴" if critical else "🟠"
            sev = "CRÍTICO" if critical else "ATENÇÃO"
            return (
                f"{icon} Seiden One — {sev}\n"
                f"{incident.get('asset_name')}\n"
                f"{incident.get('title')}\n"
                f"Módulo: {incident.get('source_module')}\n"
                f"Incidente: {incident.get('incident_id')}\n"
                f"Aberto há: {_duration_text(incident.get('opened_at'))}"
            )
        return (
            f"🟢 Seiden One — Recuperado\n"
            f"{incident.get('asset_name')}\n"
            f"{incident.get('title')}\n"
            f"Módulo: {incident.get('source_module')}\n"
            f"Incidente: {incident.get('incident_id')}\n"
            f"Duração: {_duration_text(incident.get('opened_at'), incident.get('recovered_at'))}"
        )

    def _send_phase(self, incident, phase):
        text = self._message(incident, phase)
        any_configured = False
        all_ok = True

        if self.telegram.configured:
            any_configured = True
            destination = self.telegram.chat_for(incident.get("tenant_id"))
            ok, status = self.telegram.send(incident.get("tenant_id"), text)
            self.repo.delivery(incident["incident_id"], phase, "telegram", destination, ok, "" if ok else status)
            all_ok = all_ok and ok

        if self.email.configured:
            any_configured = True
            subject = f"[Seiden One] {'Recuperado' if phase == 'recovery' else incident.get('severity','').upper()} — {incident.get('asset_name')}"
            ok, status = self.email.send(subject, text)
            self.repo.delivery(incident["incident_id"], phase, "email", ",".join(self.email.to_addresses), ok, "" if ok else status)
            all_ok = all_ok and ok

        # Do not mark as notified when no channel is configured. This allows later configuration
        # to deliver still-open incidents without losing them.
        return any_configured and all_ok

    def dispatch(self):
        for incident in self.repo.due_open():
            if self._send_phase(incident, "open"):
                self.repo.mark_phase_notified(incident["incident_id"], "open")
        if self.settings.era_notify_recovery:
            for incident in self.repo.due_recovery():
                if self._send_phase(incident, "recovery"):
                    self.repo.mark_phase_notified(incident["incident_id"], "recovery")

    def test_telegram(self):
        text = "✅ Seiden One — ERA 0.1.0\nTeste de notificação concluído com sucesso."
        ok, status = self.telegram.send("default", text)
        return {"ok": ok, "status": status}

    def test_email(self):
        ok, status = self.email.send(
            "[Seiden One] ERA 0.1.0 — Teste",
            "Seiden One — ERA 0.1.0\nTeste de notificação concluído com sucesso.",
        )
        return {"ok": ok, "status": status}
