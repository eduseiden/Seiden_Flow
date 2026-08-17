\
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from .connectors import TelegramConnector, EmailConnector
from .repository import utc_now
from tca_analytics import calculate_tca

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
    def __init__(self, repo, settings, fleet_client=None, flow_db=None):
        self.repo = repo
        self.settings = settings
        self.fleet_client = fleet_client
        self.flow_db = flow_db
        self.stop_event = threading.Event()
        self.thread = None
        self._ita_warning_last_at = 0.0
        self._ita_warning_last_code = None
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
        LOG.info("ERA 0.1.1 iniciada | poll=%ss | telegram=%s | email=%s",
                 self.settings.era_poll_seconds, self.telegram.configured, self.email.configured)

    def _run(self):
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.sync_ita()
            except RuntimeError as exc:
                self._log_ita_operational_warning(str(exc))
            except Exception:
                LOG.exception("ERA: falha inesperada ao sincronizar ITA")
            try:
                self.sync_tca()
            except Exception:
                LOG.exception("ERA: falha ao sincronizar TCA")
            try:
                self.dispatch()
            except Exception:
                LOG.exception("ERA: falha no dispatcher")
            wait = max(5, int(self.settings.era_poll_seconds) - int(time.monotonic() - started))
            self.stop_event.wait(wait)

    def _log_ita_operational_warning(self, code: str):
        """Evita traceback/spam quando o Fleet Receiver opcional está indisponível."""
        now = time.monotonic()
        # Uma mudança de erro é registrada imediatamente; repetição do mesmo estado,
        # no máximo a cada 5 minutos.
        if code != self._ita_warning_last_code or (now - self._ita_warning_last_at) >= 300:
            LOG.warning("ERA: sincronização ITA temporariamente indisponível (%s)", code)
            self._ita_warning_last_code = code
            self._ita_warning_last_at = now

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
        if not self.settings.ita_fleet_enabled:
            return
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

    def _tca_event(self, asset, key, title, severity, state, details=None):
        metadata = asset.get("metadata") or {}
        tenant_id = (
            metadata.get("tenant_id")
            or asset.get("organization_id")
            or self.settings.organization_id
            or "default"
        )
        return {
            "source_module": "TCA",
            "tenant_id": tenant_id,
            "asset_id": asset.get("asset_id") or "unknown",
            "asset_name": asset.get("name") or asset.get("asset_id") or "Ativo TCA",
            "event_key": key,
            "event_type": "thermal_control.alert",
            "severity": severity,
            "state": state,
            "title": title,
            "timestamp": utc_now(),
            "details": details or {},
        }

    def sync_tca(self):
        if not self.settings.era_tca_enabled or not self.flow_db:
            return

        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=max(1, int(self.settings.era_tca_window_hours)))
        for asset in self.flow_db.tca_assets():
            if str(asset.get("status") or "active").lower() != "active":
                continue

            rows = self.flow_db.tca_measurements(
                asset["asset_id"],
                start.isoformat().replace("+00:00", "Z"),
                end.isoformat().replace("+00:00", "Z"),
            )
            result = calculate_tca(rows, asset, asset.get("bindings") or [], start, end)
            current = result.get("current") or {}
            classification = current.get("thermal_classification") or {}
            level = str(classification.get("level") or "no_data")
            details = {
                "temperature_c": current.get("temperature_c"),
                "direction": classification.get("direction"),
                "recommended": classification.get("recommended"),
                "temporary_tolerance": classification.get("temporary_tolerance"),
                "operational_limits": classification.get("operational_limits"),
                "trend": current.get("trend"),
                "last_update": current.get("last_update"),
            }

            warning_active = level in ("attention", "elevated_alert")
            critical_active = level == "critical"

            self.ingest(self._tca_event(
                asset,
                "temperature.attention",
                "Temperatura fora da faixa ideal",
                "warning",
                "active" if warning_active else "recovered",
                details,
            ))
            self.ingest(self._tca_event(
                asset,
                "temperature.critical",
                "Temperatura crítica fora da faixa",
                "critical",
                "active" if critical_active else "recovered",
                details,
            ))

            open_episode = next(
                (e for e in reversed(result.get("episodes") or []) if e.get("status") == "open"),
                None,
            )
            open_seconds = float((open_episode or {}).get("open_seconds") or 0)
            door_threshold_s = max(1, int(self.settings.era_tca_door_open_minutes)) * 60
            door_active = bool(open_episode and open_seconds >= door_threshold_s)
            self.ingest(self._tca_event(
                asset,
                "door.open_too_long",
                "Porta aberta por tempo excessivo",
                "warning",
                "active" if door_active else "recovered",
                {
                    "open_seconds": round(open_seconds, 1),
                    "threshold_seconds": door_threshold_s,
                    "opened_at": (open_episode or {}).get("opened_at"),
                    "door": current.get("door"),
                    "temperature_c": current.get("temperature_c"),
                },
            ))

            latest_bad_recovery = next(
                (e for e in reversed(result.get("episodes") or []) if e.get("status") == "not_recovered"),
                None,
            )
            recovery_active = bool(latest_bad_recovery and level not in ("ideal", "no_data", "invalid_profile"))
            self.ingest(self._tca_event(
                asset,
                "thermal_recovery.abnormal",
                "Recuperação térmica não concluída",
                "warning",
                "active" if recovery_active else "recovered",
                {
                    "opened_at": (latest_bad_recovery or {}).get("opened_at"),
                    "closed_at": (latest_bad_recovery or {}).get("closed_at"),
                    "baseline_temperature_c": (latest_bad_recovery or {}).get("baseline_temperature_c"),
                    "maximum_temperature_c": (latest_bad_recovery or {}).get("maximum_temperature_c"),
                    "minimum_temperature_c": (latest_bad_recovery or {}).get("minimum_temperature_c"),
                    "thermal_impact_c": (latest_bad_recovery or {}).get("thermal_impact_c"),
                    "temperature_c": current.get("temperature_c"),
                    "recommended": classification.get("recommended"),
                },
            ))

    @staticmethod
    def _fmt_temp(value):
        try:
            return f"{float(value):.1f} °C".replace(".", ",")
        except Exception:
            return None

    def _context_lines(self, incident):
        if incident.get("source_module") != "TCA":
            return []
        details = incident.get("details") or {}
        lines = []
        temp = self._fmt_temp(details.get("temperature_c"))
        if temp:
            lines.append(f"Temperatura atual: {temp}")
        recommended = details.get("recommended") or {}
        if recommended.get("min") is not None and recommended.get("max") is not None:
            lo = self._fmt_temp(recommended.get("min"))
            hi = self._fmt_temp(recommended.get("max"))
            if lo and hi:
                lines.append(f"Faixa ideal: {lo} a {hi}")
        open_seconds = details.get("open_seconds")
        if open_seconds is not None and str(incident.get("source_event_key")) == "door.open_too_long":
            try:
                lines.append(f"Porta aberta: {max(0, int(float(open_seconds))) // 60} min")
            except Exception:
                pass
        return lines

    def _message(self, incident, phase: str):
        critical = incident.get("severity") == "critical"
        context = self._context_lines(incident)
        context_text = ("\n" + "\n".join(context)) if context else ""
        if phase == "open":
            icon = "🔴" if critical else "🟠"
            sev = "CRÍTICO" if critical else "ATENÇÃO"
            return (
                f"{icon} Seiden One — {sev}\n"
                f"{incident.get('asset_name')}\n"
                f"{incident.get('title')}"
                f"{context_text}\n"
                f"Módulo: {incident.get('source_module')}\n"
                f"Incidente: {incident.get('incident_id')}\n"
                f"Aberto há: {_duration_text(incident.get('opened_at'))}"
            )
        return (
            f"🟢 Seiden One — Recuperado\n"
            f"{incident.get('asset_name')}\n"
            f"{incident.get('title')}"
            f"{context_text}\n"
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
        text = "✅ Seiden One — ERA 0.1.1\nTeste de notificação concluído com sucesso."
        ok, status = self.telegram.send("default", text)
        return {"ok": ok, "status": status}

    def test_email(self):
        ok, status = self.email.send(
            "[Seiden One] ERA 0.1.1 — Teste",
            "Seiden One — ERA 0.1.1\nTeste de notificação concluído com sucesso.",
        )
        return {"ok": ok, "status": status}
