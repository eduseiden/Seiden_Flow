# Seiden FLOW 0.6.1.4

Camada de compreensão do Seiden One. Transforma evidências em entendimento operacional.


## Painel 0.6.1.4

O painel principal agora separa:

- **Operação**: ocorrências, pessoas no local, fontes e enriquecimentos do Vision.
- **Inteligência**: catálogo das soluções analíticas, começando pelo Human Experience Analytics.

Uma ocorrência do Bridge conta uma vez. `vision.analysis_completed` é armazenado como evidência correlacionada por `source_event_id`, sem aumentar o contador de ocorrências. O portal público do HEA permanece disponível em `/hea`.

## Arquitetura unificada

O FLOW consome exclusivamente:

- `seiden_bridge_event`
- `seiden_connection_online`
- `seiden_connection_offline`
- `vision.analysis_completed`

Foram removidos o modo `hybrid` e os eventos `seiden_presence`, `seiden_reader_online` e `seiden_reader_offline`. Uma passagem EVO é contabilizada uma única vez. Eventos enriquecidos do Vision são correlacionados por `source_event_id`.


## Classificação operacional na 0.6.1.4

Mensagens brutas `mqtt.message_received` permanecem armazenadas e disponíveis para diagnóstico, mas não são contabilizadas como ocorrências operacionais nem ocupam a lista de últimas ocorrências. O painel separa **Ocorrências hoje** de **Eventos capturados hoje**.

## Migração automática da 0.6.1.4

Ao iniciar, o FLOW identifica locais duplicados dentro do mesmo site pelo nome normalizado, consolida todas as referências no registro canônico e remove apenas os registros redundantes. Não é necessário editar o banco manualmente.
