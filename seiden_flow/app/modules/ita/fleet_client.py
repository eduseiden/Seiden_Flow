
from __future__ import annotations

import json
import logging
from urllib import error, parse, request

LOGGER = logging.getLogger("seiden_flow.ita_fleet")


class ITAFleetClient:
    def __init__(self, base_url: str, read_token: str, timeout_seconds: int = 8):
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.read_token = str(read_token or "").strip()
        self.timeout_seconds = int(timeout_seconds)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.read_token)

    def _get(self, path: str):
        if not self.configured:
            raise RuntimeError("fleet_not_configured")
        req = request.Request(
            self.base_url + path,
            headers={
                "Authorization": f"Bearer {self.read_token}",
                "Accept": "application/json",
                "User-Agent": "Seiden-Flow-ITA/0.3.1.8",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8"))
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            LOGGER.warning("Fleet Receiver HTTP %s em %s: %s", exc.code, path, detail)
            raise RuntimeError(f"receiver_http_{exc.code}") from exc
        except error.URLError as exc:
            LOGGER.warning("Fleet Receiver indisponível em %s: %s", path, exc.reason)
            raise RuntimeError("receiver_unavailable") from exc
        except TimeoutError as exc:
            LOGGER.warning("Timeout no Fleet Receiver em %s", path)
            raise RuntimeError("receiver_timeout") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning("Resposta inválida do Fleet Receiver em %s", path)
            raise RuntimeError("receiver_invalid_json") from exc

    def _write(self, method: str, path: str, payload=None, extra_headers=None):
        if not self.configured:
            raise RuntimeError("fleet_not_configured")
        headers = {
            "Authorization": f"Bearer {self.read_token}",
            "Accept": "application/json",
            "User-Agent": "Seiden-Flow-ITA/0.3.1.8",
        }
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if extra_headers:
            headers.update(extra_headers)
        req = request.Request(self.base_url + path, headers=headers, data=data, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            LOGGER.warning("Fleet Receiver HTTP %s em %s %s: %s", exc.code, method, path, detail)
            raise RuntimeError(f"receiver_http_{exc.code}") from exc
        except error.URLError as exc:
            LOGGER.warning("Fleet Receiver indisponível em %s %s: %s", method, path, exc.reason)
            raise RuntimeError("receiver_unavailable") from exc
        except TimeoutError as exc:
            LOGGER.warning("Timeout no Fleet Receiver em %s %s", method, path)
            raise RuntimeError("receiver_timeout") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning("Resposta inválida do Fleet Receiver em %s %s", method, path)
            raise RuntimeError("receiver_invalid_json") from exc

    def fleet(self, view: str = "active"):
        view = str(view or "active").strip().lower()
        return self._get("/fleet?" + parse.urlencode({"view": view}))

    def asset(self, pulse_id: str):
        return self._get("/fleet/" + parse.quote(str(pulse_id), safe=""))

    def set_asset_status(self, pulse_id: str, status: str, reason: str = ""):
        qid = parse.quote(str(pulse_id), safe="")
        return self._write(
            "POST",
            f"/fleet/{qid}/asset-status",
            {"status": status, "reason": reason},
        )

    def delete_asset(self, pulse_id: str):
        qid = parse.quote(str(pulse_id), safe="")
        return self._write(
            "DELETE",
            f"/fleet/{qid}",
            None,
            {"X-Seiden-Confirm-Pulse": str(pulse_id)},
        )
