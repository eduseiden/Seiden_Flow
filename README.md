# Seiden FLOW 0.23.0

## ERA 0.1.0 — Event Response Automation

Primeira versão da camada transversal de resposta operacional da Seiden One.

### ERA 0.1.0

- Incident Engine com correlação e deduplicação.
- Estados `open` e `recovered`.
- Políticas independentes para crítico, atenção e ausência de telemetria.
- Detecção server-side de ausência de telemetria ITA.
- Sincronização dos alertas ativos do ITA.
- Conector Telegram via bot.
- Conector e-mail via SMTP.
- Notificações de abertura e recuperação.
- Auditoria de tentativas de entrega.
- API transversal `/api/v1/era/events` para qualquer módulo Seiden One.
- Portal `/era`.

### Segurança e arquitetura

A ERA não altera o princípio zero-control da Seiden Pulse. Ela reage a eventos
e aciona canais externos; não controla o host monitorado.

Telegram e e-mail nascem desabilitados e precisam ser explicitamente configurados.
