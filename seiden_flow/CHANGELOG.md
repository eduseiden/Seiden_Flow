# Changelog

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
