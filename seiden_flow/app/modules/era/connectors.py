\
from __future__ import annotations

import json
import smtplib
import ssl
from email.message import EmailMessage
from urllib import request, error


class TelegramConnector:
    def __init__(self, enabled: bool, bot_token: str, default_chat_id: str, routes: tuple[str, ...] = ()):
        self.enabled = bool(enabled)
        self.bot_token = str(bot_token or "").strip()
        self.default_chat_id = str(default_chat_id or "").strip()
        self.routes = self._parse_routes(routes)

    @staticmethod
    def _parse_routes(routes):
        result = {}
        for item in routes or ():
            raw = str(item or "").strip()
            if "|" not in raw:
                continue
            tenant, chat = raw.split("|", 1)
            tenant, chat = tenant.strip(), chat.strip()
            if tenant and chat:
                result[tenant] = chat
        return result

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.bot_token) and bool(self.default_chat_id or self.routes)

    def chat_for(self, tenant_id: str) -> str:
        return self.routes.get(str(tenant_id or "").strip(), self.default_chat_id)

    def send(self, tenant_id: str, text: str) -> tuple[bool, str]:
        if not self.enabled:
            return False, "telegram_disabled"
        if not self.bot_token:
            return False, "telegram_token_missing"
        chat_id = self.chat_for(tenant_id)
        if not chat_id:
            return False, "telegram_chat_missing"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        body = json.dumps(
            {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            ensure_ascii=False,
        ).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=15, context=ssl.create_default_context()) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                payload = json.loads(raw) if raw else {}
                return bool(payload.get("ok")), "ok" if payload.get("ok") else "telegram_rejected"
        except error.HTTPError as exc:
            return False, f"telegram_http_{exc.code}"
        except Exception as exc:
            return False, f"telegram_error:{type(exc).__name__}"


class EmailConnector:
    def __init__(
        self,
        enabled: bool,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        to_addresses: tuple[str, ...],
        starttls: bool = True,
    ):
        self.enabled = bool(enabled)
        self.host = str(host or "").strip()
        self.port = int(port or 587)
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.from_address = str(from_address or "").strip()
        self.to_addresses = tuple(str(x).strip() for x in (to_addresses or ()) if str(x).strip())
        self.starttls = bool(starttls)

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.host and self.from_address and self.to_addresses)

    def send(self, subject: str, text: str) -> tuple[bool, str]:
        if not self.enabled:
            return False, "email_disabled"
        if not self.configured:
            return False, "email_not_configured"

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(self.to_addresses)
        msg.set_content(text)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                if self.starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
            return True, "ok"
        except Exception as exc:
            return False, f"email_error:{type(exc).__name__}"
