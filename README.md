# Seiden FLOW 0.6.0

Camada de compreensão do Seiden One. Transforma evidências em entendimento operacional.

## Arquitetura unificada

O FLOW consome exclusivamente:

- `seiden_bridge_event`
- `seiden_connection_online`
- `seiden_connection_offline`
- `vision.analysis_completed`

Foram removidos o modo `hybrid` e os eventos `seiden_presence`, `seiden_reader_online` e `seiden_reader_offline`. Uma passagem EVO é contabilizada uma única vez. Eventos enriquecidos do Vision são correlacionados por `source_event_id`.
