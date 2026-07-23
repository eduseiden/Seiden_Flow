# Seiden FLOW 0.1.0

## Objetivo

O FLOW é a camada de dados operacional da Seiden Tech. Ele recebe eventos, preserva o evento original, normaliza os campos principais, mantém estado operacional e disponibiliza os dados por API e exportação.

## Fontes suportadas

### Seiden Bridge

Por padrão, o FLOW assina automaticamente estes eventos do Home Assistant:

- `seiden_presence`
- `seiden_reader_online`
- `seiden_reader_offline`

Não é necessário alterar o Bridge 0.6.1.

### Seiden Vision

No Vision 0.4.0, configure:

```yaml
webhook_enabled: true
webhook_url: http://SEU_HOME_ASSISTANT:8100/api/v1/events
webhook_api_key: ""
```

Quando o add-on é acessado apenas por Ingress, a porta pode não estar exposta na rede. Para o primeiro teste, pode-se enviar o evento pela API interna ou acrescentar mapeamento de porta em uma versão posterior. O endpoint oficial é `/api/v1/events`.

## API

### Ingerir evento

```http
POST /api/v1/events
Content-Type: application/json
Authorization: Bearer TOKEN
```

A chave só é exigida quando `api_key` está preenchido.

### Consultas

- `GET /api/v1/health`
- `GET /api/v1/summary`
- `GET /api/v1/events`
- `GET /api/v1/state/people`
- `GET /api/v1/state/people/inside`
- `GET /api/v1/state/sources`
- `GET /api/v1/export/events.json`
- `GET /api/v1/export/events.csv`

## Entidades no Home Assistant

- `sensor.seiden_flow_people_inside`
- `sensor.seiden_flow_events_today`
- `sensor.seiden_flow_sources_offline`

## Persistência

Banco SQLite em `/config/seiden_flow.db`, dentro do armazenamento persistente do add-on.

## Observação arquitetural

O serviço não usa entidades do Home Assistant como banco. O HA é uma fonte e um consumidor. O contrato principal do FLOW é sua API e seu banco operacional.
