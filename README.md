# Seiden FLOW 0.5.2.2

## Integração com Seiden Bridge 0.8.3 e Seiden Vision 0.4.1

O FLOW pode consumir o evento unificado `seiden_bridge_event`, os eventos técnicos `seiden_connection_online` e `seiden_connection_offline` e o evento enriquecido `vision.analysis_completed`. Durante a migração, `bridge_source_mode: hybrid` mantém também os eventos legados. Após validar toda a cadeia, use `bridge_source_mode: unified` e desative o legado no Bridge. O Vision 0.4.1 pode continuar entregando `vision.analysis_completed` por webhook para `/api/v1/ingest`; a assinatura no Home Assistant fica pronta para publicação direta futura.


Dashboard Polish: novo Seiden Design System, temas claro/escuro/sistema, responsividade real para desktop, tablet e celular, gauge do Experience Index, linguagem de negócio, estados de carregamento e apresentação móvel dos resultados por fonte.
