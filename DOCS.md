# Seiden FLOW 0.6.0

Camada de compreensão do Seiden One. Transforma evidências em entendimento operacional.

## Arquitetura unificada

O FLOW consome exclusivamente:

- `seiden_bridge_event`
- `seiden_connection_online`
- `seiden_connection_offline`
- `vision.analysis_completed`

Foram removidos o modo `hybrid` e os eventos `seiden_presence`, `seiden_reader_online` e `seiden_reader_offline`. Uma passagem EVO é contabilizada uma única vez. Eventos enriquecidos do Vision são correlacionados por `source_event_id`.


### Eventos brutos e ocorrências

`mqtt.message_received` é um evento bruto de captura. Ele é persistido para rastreabilidade, mas não é considerado ocorrência operacional até que o FLOW produza um entendimento de nível superior.
