# Changelog

## 0.2.0
- Novo modelo de domínio: Organization, Site, Location, Source, Person, Event e Presence.
- Migração automática e não destrutiva do banco da versão 0.1.0.
- APIs de domínio em `/api/v1/domain/*`.
- WebSocket do Home Assistant com leitura sem falso timeout, heartbeat e reconexão com backoff.
- Nova entidade `sensor.seiden_flow_ha_connection`.
- Dashboard ampliado com métricas do domínio e saúde da conexão.
- APIs, exportações e entidades da versão 0.1.0 preservadas.

## 0.1.0
- Primeira versão da camada de dados operacional.
