# Changelog

## 0.7.1 — Environmental Storage
- Assinatura nativa do evento `environment.observation` produzido pelo Seiden Vision 0.6.1.
- Nova persistência `environmental_measurements` para temperatura, umidade, condição, Comfort Score e saúde da fonte.
- Deduplicação por `event_id` e `source_event_id`, impedindo regravação do mesmo evento ambiental.
- Validação de contrato, unidades, limites físicos e timestamps UTC antes do armazenamento.
- Novas APIs internas: `/api/v1/environment/measurements`, `/api/v1/environment/latest` e `/api/v1/environment/summary`.
- Nenhuma alteração no HEA, nas ocorrências operacionais ou nos cálculos existentes.

## 0.7.0.1
- O card **Fontes** do HEA passa a contar fontes canônicas, e não IDs históricos distintos.
- Observações legadas e atuais com o mesmo nome normalizado e local são consolidadas na métrica e no detalhamento por fonte.
- Nenhuma alteração nos cálculos do Experience Index, confiança ou distribuição de expressões.

## 0.7.0
- Adoção do Seiden One Platform Standard v1.0.
- Fuso de exibição configurável por `timezone`.
- Formato visual padronizado em `YYYY-MM-DD HH:MM:SS`.
- Conversão consistente de eventos UTC, AWS, Bridge e Vision nas telas Operação e HEA.
- Registros históricos sem offset permanecem exibidos sem deslocamento retroativo.

## 0.7.0 — Consolidação definitiva das fontes HEA

- Migração direta dos IDs históricos em `observations` e `observation_aggregates`, independentemente da tabela `sources`.
- Seleção da fonte canônica pelo nome normalizado, priorizando a fonte operacional do Seiden Bridge.
- Remoção segura de agregados duplicados da mesma janela analítica.
- Deduplicação defensiva no seletor de fontes do HEA, impedindo nomes repetidos mesmo diante de resíduos históricos.
- Migração idempotente executada automaticamente ao iniciar o FLOW.

## 0.6.1.5 — Deduplicação segura de fontes

- Migração automática de fontes duplicadas por site, tipo e nome normalizado.
- Prioriza como fonte canônica o registro operacional criado pelo Seiden Bridge.
- Consolida referências em eventos, observações e agregados HEA.
- Corrige fontes duplicadas no filtro do painel HEA, inclusive quando o source_id antigo não existia na tabela de fontes.
- Proteção preventiva para reutilizar a fonte existente em novos eventos.
- Migração idempotente, sem necessidade de limpeza manual ou reinício do Home Assistant.

## 0.6.1.4 — Deduplicação segura de locais

- Migração automática de locais duplicados por site e nome normalizado.
- Referências em fontes, presenças, eventos, observações e agregados HEA são consolidadas no local canônico.
- Proteção preventiva: novas mensagens reutilizam um local existente com o mesmo nome em vez de criar outro registro.
- Migração idempotente, sem necessidade de limpeza manual do banco.

## 0.6.1.3

- Mensagens `mqtt.message_received` deixam de ser tratadas como ocorrências operacionais.
- Últimas ocorrências passam a mostrar fatos operacionais, preservando eventos MQTT brutos no banco.
- Novo indicador “Eventos capturados hoje” separa volume técnico de acontecimentos operacionais.
- Análises pendentes passam a considerar apenas autenticações das últimas 24 horas.
- Mantidas a navegação Operação/Inteligência e a publicação independente do HEA em `/hea`.

# Changelog

## 0.6.1.3 — Operação e Inteligência

- Novo painel principal orientado à operação.
- Eventos do Bridge passam a ser exibidos e contados como ocorrências operacionais.
- Eventos `vision.analysis_completed` são tratados como evidências enriquecidas, correlacionadas por `source_event_id`.
- Contadores separados para ocorrências, análises concluídas e análises pendentes.
- Nova navegação por abas: **Operação** e **Inteligência**.
- HEA passa a ser apresentado como a primeira solução de inteligência do FLOW.
- Portal web independente do HEA preservado integralmente em `/hea`.
- Nova rota alias `/intelligence/hea` e APIs de ocorrências.
- Sensor `sensor.seiden_flow_events_today` passa a representar ocorrências hoje, preservando o entity_id existente.
- Novo sensor `sensor.seiden_flow_vision_analyses_today`.

## 0.6.0 — Arquitetura unificada sem legado

- Remove `bridge_source_mode` e todos os eventos legados.
- Consome apenas os eventos unificados do Bridge e do Vision.
- Elimina a dupla contabilização no modo híbrido.

# Changelog

## 0.5.2.2 — Arquitetura unificada Bridge/Vision

- Consumo nativo do evento unificado `seiden_bridge_event` do Seiden Bridge 0.8.3.
- Consumo dos eventos genéricos `seiden_connection_online` e `seiden_connection_offline`.
- Novo modo de origem `bridge_source_mode`: `unified`, `legacy` ou `hybrid`.
- Compatibilidade temporária com `seiden_presence`, `seiden_reader_online` e `seiden_reader_offline`.
- Assinatura preparada para `vision.analysis_completed`, mantendo também a ingestão HTTP/webhook já existente.
- Normalização de `connection`, `subject.external_id` e eventos técnicos genéricos.
- Duplicidades da fase híbrida continuam protegidas por `event_id`.


## 0.5.2.1 — Dashboard Polish

- Novo Seiden Design System baseado em variáveis CSS.
- Temas Claro, Escuro e Seguir Sistema, persistidos no navegador.
- Layout responsivo dedicado para desktop, tablet e celular.
- Gauge visual do Experience Index entre Crítico e Excelente.
- Resultados por fonte convertidos em cards no celular.
- Linguagem técnica substituída por mensagens orientadas ao negócio.
- Melhor e pior período renomeados para melhor e pior momento.
- Estados de carregamento com skeleton e microanimações discretas.
- Tooltips, foco por teclado, contraste aprimorado e suporte a redução de movimento.
- Identidade visual e assinatura Powered by Seiden FLOW.

## 0.5.2 — Epic 2: Dashboard Analytics

- Novo gráfico de evolução temporal do Experience Index.
- Agregação automática dos pontos conforme período e volume de observações.
- O gráfico só é exibido com pelo menos três intervalos analíticos válidos.
- Mensagens específicas para amostragem insuficiente, apenas um intervalo ou poucos períodos.
- Melhor e pior período exigem pelo menos dois intervalos válidos, evitando resultados idênticos sem significado analítico.
- Card “Predominância” renomeado para “Categoria predominante”, com percentual explícito.
- Nova interpretação textual distingue frequência predominante de saldo emocional ponderado.
- Metadados analíticos adicionados ao resumo: `history_points`, `trend_chart_available`, `trend_chart_status` e `aggregation_seconds`.

## 0.5.1 — Epic 1: Experience Index 2.0

- Novo motor analítico independente da interface.
- Cálculo por emoção com pesos próprios e ponderação pela confiança da análise.
- Escala normalizada de -100 a +100.
- Classificação textual do índice.
- Comparação automática com período anterior equivalente.
- Tendência: melhorando, estável ou piorando.
- Variação absoluta e percentual.
- Confiança média e número de observações.
- Distribuição por categoria e por emoção original.
- Melhor e pior intervalo do período selecionado.
- Novo contrato interno `GET /api/v2/experience`.
- Portal HEA atualizado para exibir o Experience Index 2.0.
- Sensor do Home Assistant enriquecido com os novos atributos analíticos.

### Observação

A variação percentual não é exibida quando o índice anterior está entre -1 e +1, pois a divisão próxima de zero produz resultados matematicamente instáveis e potencialmente enganosos.
