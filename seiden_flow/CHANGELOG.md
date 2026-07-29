# Changelog

## 0.9.3.2

- traduz estados positivos como `within_optimal_range` para “Dentro da faixa ideal”;
- trata valores de bateria fora de 0–100% na apresentação;
- transforma o contexto técnico em seção expansível de largura integral;
- exibe o identificador curto do ruleset, preservando o valor completo em tooltip;
- compacta a grade e remove grandes vazios visuais;
- contextualiza observações com o período efetivamente selecionado;
- remove indicadores redundantes de extrapolação da escala;
- apresenta o valor medido junto ao limite ultrapassado;
- preserva o rodapé `Powered by Seiden One Intelligence`;
- mantém `DATABASE_SCHEMA_VERSION = 9`, sem nova migração.

## 0.9.3.1

- atualiza o README da raiz para a versão corrente;
- substitui “Qualidade dos dados” por contagem de observações no período;
- completa a tradução dos `reason_codes` e adiciona fallback legível;
- destaca o motivo principal no card de condição atual;
- detalha faixas ideal, atenção e limites críticos;
- sinaliza valores abaixo ou acima da escala exibida;
- traduz tipos de análise, estado operacional e origem das regras;
- preserva rulesets longos sem truncamento visual;
- adiciona saúde da fonte com bateria, sinal e último contato;
- reorganiza a grade para perfis sem umidade;
- padroniza o rodapé como `Powered by Seiden One Intelligence`;
- mantém `DATABASE_SCHEMA_VERSION = 9`, sem nova migração.

## 0.9.3

- adiciona suporte aos perfis ambientais autoritativos do Seiden Vision 0.8.3.1;
- armazena `analysis_type`, `environmental_score`, `operational_state`, perfil resolvido, faixas aplicadas, scores por métrica e motivos;
- aceita a condição `critical` emitida pelo Vision;
- diferencia conforto humano, conformidade ambiental e leitura informativa;
- oculta umidade quando o perfil possui `humidity: null`;
- apresenta barras visuais usando exclusivamente `applied_ranges`;
- atualiza a visão de portfólio com perfil, condição e score ambiental;
- migra o banco para o schema 9 sem recriar a base existente.

# 0.9.2.3

- adiciona escala visual progressiva ao EEA Index, de 0 a 100;
- posiciona marcador proporcional ao índice do período;
- explicita as faixas Crítico, Desconfortável, Atenção e Confortável;
- adiciona ajuda contextual sobre cálculo e cobertura do índice;
- mostra a base observada e a confiabilidade junto ao EEA Index;
- adiciona escala compacta nos cards da visão de portfólio;
- padroniza o título visual para `EEA Index`;
- não altera o schema do banco.

# 0.9.2.2

## Consolidação de identidades e visão de portfólio

- consolida fontes ambientais legadas que diferem apenas por maiúsculas, acentos ou separadores;
- preserva aliases históricos de `source_id` e `location_id` sem apagar medições do SQLite;
- usa a identidade mais recente e amigável como identidade canônica nos filtros;
- inclui o histórico legado ao consultar a fonte canônica;
- adiciona `GET /api/v1/environment/portfolio`;
- substitui a análise global sem significado por uma visão individual de todas as fontes;
- mantém o dashboard analítico completo somente quando um sensor específico é selecionado;
- não calcula média global de temperatura ou umidade entre ambientes distintos;
- preserva `DATABASE_SCHEMA_VERSION = 8`, sem migração.

# 0.9.2.1

## Correções de estabilidade

- corrige o carregamento do EEA após falha HTTP 500 no endpoint agregado;
- retorna o portal a endpoints ambientais sequenciais e já validados, sem requisições sobrepostas;
- mantém cache de 30 segundos, pausa em aba oculta e cancelamento de requisições;
- torna o catálogo de fontes opcional, evitando que sua falha derrube o painel;
- adiciona logs completos de exceção ao endpoint agregado;
- atualiza o rodapé do HEA para `Powered by Seiden One Intelligence`.

# 0.9.2

## Environmental Sources

- adiciona filtros de EEA por `location_id` e `source_id`;
- adiciona catálogo de fontes ambientais em `GET /api/v1/environment/sources`;
- apresenta nomes amigáveis, local, quantidade de medições e última leitura;
- adiciona seleção direta de uma fonte a partir dos cards do dashboard;
- adiciona a assinatura `Powered by Seiden One Intelligence`;
- preserva `DATABASE_SCHEMA_VERSION = 8`, sem migração.

## Performance e estabilidade

- substitui as chamadas paralelas de analytics e timeline por um único endpoint `GET /api/v1/environment/dashboard`;
- adiciona cache em memória de 30 segundos, limitado a 32 entradas;
- impede sobreposição de atualizações e cancela requisições obsoletas;
- pausa o auto refresh quando a aba não está visível;
- remove o `setInterval`, adotando agendamento somente após a conclusão da atualização anterior;
- reduz o Gunicorn para quatro threads e adiciona reciclagem preventiva do worker;
- registra o tempo das consultas ambientais, elevando para warning operações acima de 500 ms.


- Adiciona o EEA à área **Inteligência** do painel principal, com acesso direto e resumo das últimas 24 horas.
- Classifica textualmente o EEA Index médio do período.
- Torna a cobertura mais transparente, exibindo minutos observados sobre o total do período.
- Adiciona marcadores visuais e tooltips aos gráficos.
- Implementa gráfico climático com dois eixos: temperatura à esquerda e umidade à direita.
- Melhora a leitura dos gráficos e preserva o schema de banco na versão 8.

# 0.9.0

- Adiciona o primeiro dashboard Environmental Experience Analytics em `/environment`.
- Exibe EEA Index, condição atual, temperatura, umidade e cobertura de dados.
- Inclui distribuição por condição, timeline, melhor/pior período e leitura operacional.
- Adiciona filtros de período e agrupamento, suporte a Ingress e timezone operacional.
- Integra o acesso ao EEA na área de Inteligência do dashboard principal.
- Mantém o schema de banco na versão 8.

## 0.8.1.3

- Hotfix: restaura `SCHEMA_VERSION` e `DATABASE_SCHEMA_VERSION = 8` em `app/version.py`, corrigindo a inicialização do FLOW.

## 0.8.1.3 — EEA Current Condition Consistency

- Recalcula `current.condition` com o mesmo ruleset aplicado aos agregados, à timeline e à distribuição.
- Preserva a condição original do Vision no campo `current.source_condition`.
- Expõe `current.condition_source` como `eea_ruleset` para rastreabilidade da classificação.
- Mantém o schema do banco na versão 8, sem migração.

## 0.8.1.1 — EEA Analytics Consistency

- Deriva a condição dos períodos agregados a partir do `comfort_score` médio.
- Padroniza as faixas do EEA: `comfortable` (85–100), `attention` (70–84,99), `uncomfortable` (50–69,99) e `critical` (0–49,99).
- Aplica as mesmas faixas à timeline e à distribuição das amostras observadas.
- Renomeia `estimated_minutes` para `observed_minutes`, evitando interpretar lacunas de cobertura como tempo real medido.
- Mantém o schema do banco na versão 8, sem migração.

## 0.8.1 — EEA Analytics Engine

- Introduz o motor Environmental Experience Analytics em `environmental_analytics.py`.
- Nova API `GET /api/v1/environment/analytics` com EEA Index, estatísticas, distribuição de condições, tendência, melhor/pior período e qualidade dos dados.
- Nova API `GET /api/v1/environment/timeline` com agregação temporal configurável.
- Normalização analítica por fonte e janela temporal, preservando todos os eventos brutos no banco.
- Comparação automática com o período imediatamente anterior.
- Filtros por período, intervalo personalizado, fonte e local.
- Nenhuma mudança no schema SQLite; `DATABASE_SCHEMA_VERSION` permanece em 8.

## 0.8.0 — Consolidação de versão e documentação

- Alinha a versão exibida no add-on, no runtime, nas APIs e na documentação.
- Consolida o Environmental Storage e suas APIs como baseline oficial do FLOW.
- Sincroniza `README.md` e `DOCS.md` com os eventos atualmente consumidos.
- Nenhuma alteração no banco de dados, no HEA, no EEA ou nos contratos de eventos existentes.

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

## 0.9.2.2

## Consolidação de identidades e visão de portfólio

- consolida fontes ambientais legadas que diferem apenas por maiúsculas, acentos ou separadores;
- preserva aliases históricos de `source_id` e `location_id` sem apagar medições do SQLite;
- usa a identidade mais recente e amigável como identidade canônica nos filtros;
- inclui o histórico legado ao consultar a fonte canônica;
- adiciona `GET /api/v1/environment/portfolio`;
- substitui a análise global sem significado por uma visão individual de todas as fontes;
- mantém o dashboard analítico completo somente quando um sensor específico é selecionado;
- não calcula média global de temperatura ou umidade entre ambientes distintos;
- preserva `DATABASE_SCHEMA_VERSION = 8`, sem migração.

# 0.9.2.1

- corrige o carregamento do EEA após falha HTTP 500 no endpoint agregado;
- retorna o portal a endpoints ambientais sequenciais e já validados, sem requisições sobrepostas;
- mantém cache de 30 segundos, pausa em aba oculta e cancelamento de requisições;
- torna o catálogo de fontes opcional, evitando que sua falha derrube o painel;
- adiciona logs completos de exceção ao endpoint agregado;
- atualiza o rodapé do HEA para `Powered by Seiden One Intelligence`.


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

## 0.9.2.2

## Consolidação de identidades e visão de portfólio

- consolida fontes ambientais legadas que diferem apenas por maiúsculas, acentos ou separadores;
- preserva aliases históricos de `source_id` e `location_id` sem apagar medições do SQLite;
- usa a identidade mais recente e amigável como identidade canônica nos filtros;
- inclui o histórico legado ao consultar a fonte canônica;
- adiciona `GET /api/v1/environment/portfolio`;
- substitui a análise global sem significado por uma visão individual de todas as fontes;
- mantém o dashboard analítico completo somente quando um sensor específico é selecionado;
- não calcula média global de temperatura ou umidade entre ambientes distintos;
- preserva `DATABASE_SCHEMA_VERSION = 8`, sem migração.

# 0.9.2.1

- corrige o carregamento do EEA após falha HTTP 500 no endpoint agregado;
- retorna o portal a endpoints ambientais sequenciais e já validados, sem requisições sobrepostas;
- mantém cache de 30 segundos, pausa em aba oculta e cancelamento de requisições;
- torna o catálogo de fontes opcional, evitando que sua falha derrube o painel;
- adiciona logs completos de exceção ao endpoint agregado;
- atualiza o rodapé do HEA para `Powered by Seiden One Intelligence`.


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
