# Seiden FLOW 0.20.0

## 0.20.0 — Infrastructure Thermal Analytics (ITA) 0.1.0

Nova versão funcional do Seiden Flow, construída sobre a baseline bilíngue 0.19.0.3.

- Adiciona **ITA — Infrastructure Thermal Analytics** como quinto módulo analítico.
- Consome `infrastructure.telemetry_snapshot` do Seiden Bridge.
- Arquitetura **vendor-agnostic**, baseada em semântica de telemetria (`physical_context`, unidades, saúde, thresholds e relações), sem dependência de IDs específicos de fabricante.
- Persiste histórico por sistema e sensor e calcula visão térmica consolidada, deltas, potência, ventilação e distância para thresholds nativos.
- Adiciona portal ITA bilíngue PT/EN e APIs `/api/v1/ita/*`.
- Database Schema atualizado para **20**.
- HEA, EEA, TCA, LCA e a fundação global PT/EN + Light/System/Dark da 0.19.0.3 são preservados.


## 0.19.0.3 — Residual i18n Audit & Polish

Patch release focused exclusively on presentation. No analytics, ingestion, MQTT, database, API or module business logic was changed.

- Standardizes PT/EN and Light/System/Dark selectors across FLOW, HEA, EEA, TCA and LCA using the FLOW home visual convention.
- Expands English coverage for static and dynamically generated UI text, including tooltips, placeholders, empty states, runtime status messages and labels.
- Improves runtime translation observation so text updated after page load is translated consistently.
- Keeps TCA at 0.6.0, LCA at 0.5.0.1 and database schema at 19.


## Global UX Foundation — PT/EN + Light/System/Dark

Esta release adiciona uma camada transversal de experiência à Seiden One sem alterar
a lógica operacional ou analítica dos módulos. **Flow, HEA, EEA, TCA e LCA** passam
a compartilhar preferência global de idioma e aparência.

- idioma global persistente: **PT-BR / EN-US**;
- aparência global persistente: **Light / System / Dark**;
- TCA recebe suporte completo a tema escuro, preservando sua UX 0.6.0;
- LCA passa a usar a mesma chave global de tema dos demais módulos;
- datas e números apresentados pela interface respeitam o idioma selecionado;
- textos estáticos e conteúdos renderizados dinamicamente recebem tradução na camada de UI;
- nenhuma alteração em banco, schema, ingestão, MQTT, correlação, analytics ou regras de negócio.

As versões funcionais dos módulos permanecem inalteradas: **TCA 0.6.0** e **LCA 0.5.0.1**.
Database Schema permanece **19**.


## TCA 0.6.0 — UX Foundation

A primeira evolução comercial do TCA reorganiza a experiência em três perspectivas
sobre os mesmos dados: **Operação**, **Executivo** e **Análise**.

A interface é adaptativa e pensada para uso real em tablet, desktop e celular.
O dispositivo influencia a apresentação, mas nunca remove informação: a análise
completa de cada ativo permanece sempre acessível.

A visão Operação aplica **Exceptions First** e mostra imediatamente se existe algum
ativo que exige atenção. A visão Executiva resume a condição atual da operação.
A visão Análise preserva todos os recursos técnicos e históricos já existentes.

Esta release não adiciona multi-site nem muda a inteligência térmica existente.
O foco é validar UX/UI com dados reais antes da próxima camada funcional.


## LCA 0.5.0.1 — MQTT State Driver topic compatibility

O LCA passa a aceitar qualquer tópico MQTT que já tenha sido explicitamente
normalizado pelo **Seiden Bridge MQTT State Driver** como `state_transition`.
O filtro legado `lca_topic_prefixes` continua valendo apenas para payloads MQTT brutos.

Isso permite, por exemplo:

`zigbee2mqtt/ReleCozinhaBancada` → Bridge `state_transition` → LCA canal `main`.


## LCA 0.5.0 — Behavioral Patterns

A Seiden One passa a aprender **o que é normal no comportamento da iluminação**
antes de destacar o que está diferente.

A nova camada analítica inclui:

- perfis aprendidos de duração por circuito;
- sequências recorrentes entre circuitos;
- circuitos que costumam permanecer ligados juntos;
- horários típicos de início;
- identificação conservadora de uso prolongado, horário incomum e frequência incomum;
- confiança explícita em toda conclusão.

A confiança não depende apenas do número de dias. Ela combina **tempo observado,
volume de sessões e consistência do padrão**. Enquanto a base ainda é pequena,
a interface mostra claramente `Padrão ainda em formação`.

O Behavioral Patterns utiliza exclusivamente as sessões canônicas já existentes
e não altera a lógica estabilizada de ingestão, correlação ou estado do LCA.


## LCA 0.4.2 — Interaction Preference

A Seiden One passa a compreender **como as pessoas preferem interagir com a iluminação**,
indo além de quando e por quanto tempo os circuitos são utilizados.

A nova camada analítica mostra:

- pontos de acionamento mais utilizados;
- direto × paralelo × cena;
- local × remoto × automação × origem não identificada;
- preferência dominante por circuito;
- mudanças de preferência em relação ao período anterior.

A análise utiliza exclusivamente os eventos operacionais já consolidados pelo LCA
e não altera a lógica estabilizada de correlação, estado canônico ou sessões.


## LCA 0.4.0.2 — Bridge State Transition Support

O LCA agora consome `state_transition` do MQTT State Driver. Pontos diretos atualizam o circuito canônico; paralelos continuam usando a interação explícita do Node-RED para identificar a origem. O estado MQTT, por si só, nunca é classificado automaticamente como acionamento local.


## LCA 0.4.0.2 — Circuit Usage UX Refinement

A primeira camada temporal do LCA transforma estados canônicos ON/OFF em sessões de iluminação por circuito. O dashboard passa a mostrar tempo ligado, quantidade de sessões, duração média, maior sessão e utilização percentual por circuito, preservando toda a linguagem visual e o dark mode consolidados na série 0.3.9.

### Fundamentos preservados

- estado canônico por circuito continua sendo a fonte única de verdade;
- pontos diretos e paralelos permanecem formas de acionamento, não fontes independentes de estado;
- infraestrutura continua baseada no dispositivo MQTT e canais L1/L2/L3;
- UX/UI, histórico operacional, bolinhas de estado e dark mode da LCA 0.3.9 são mantidos.

### Novidades 0.4.0.2

- correção gramatical de `sessão/sessões`;
- exibição padrão somente dos circuitos que tiveram uso no período;
- filtro por local na seção **Tempo de uso**;
- opção **Mostrar sem uso**, desativada por padrão;
- KPIs recalculados de forma coerente com o local selecionado;
- ordenação por maior tempo ligado mantida como padrão;
- novos controles revisados para responsividade e dark mode;
- nenhuma alteração de schema ou da lógica canônica de sessões.

## Base anterior — LCA 0.3.9.3 — Canonical Circuit State

Correção arquitetural do estado atual dos circuitos, preservando integralmente a UX/UI da série LCA 0.3.9.

- cada circuito lógico passa a ter um estado canônico persistente próprio em `lca_circuit_state`;
- o estado do circuito deixa de ser inferido do estado técnico de pontos diretos/paralelos;
- uma interação confirmada atualiza o estado canônico pelo `requested_state`;
- a migração inicializa o estado preferencialmente pela última interação confirmada e usa telemetria de canal apenas como baseline quando não existe histórico lógico;
- cabeçalho e **Circuitos monitorados** leem a mesma fonte de verdade;
- atualizações fora de ordem não sobrescrevem um estado lógico mais recente;
- todos os refinamentos visuais, dark mode, identidade MQTT, L1/L2/L3 e histórico operacional da LCA 0.3.9 são mantidos;
- Database Schema `18`; HEA, EEA e TCA preservados.

## LCA 0.3.7 — identidade de infraestrutura por dispositivo MQTT

O LCA passa a considerar como infraestrutura apenas os dispositivos reais descobertos pelos tópicos MQTT (por exemplo, `zigbee2mqtt/Interruptor Sala`) e seus canais canônicos (`L1`, `L2`, ...). Entidades amigáveis do Home Assistant, como `switch.sala_painel_virtual`, permanecem apenas como metadado técnico do evento e não aparecem como dispositivos ou teclas adicionais.

- dispositivo = tópico/dispositivo Zigbee2MQTT;
- tecla = canal canônico L1/L2/L3/...;
- nomes livres de entidades não criam infraestrutura;
- interações com entidades renomeadas são correlacionadas pelo circuito e pela transição MQTT real;
- interações que chegam antes da transição ficam pendentes por alguns segundos e são resolvidas quando o estado real chega;
- dispositivos sintéticos criados por versões anteriores a partir de `seiden/lca/interactions` são ocultados automaticamente quando não possuem evidência real de estado;
- Database Schema `17`; HEA, EEA e TCA preservados.

## LCA 0.3.6 — consolidação de circuitos lógicos

Esta versão separa definitivamente **circuitos de iluminação** de **pontos de acionamento**. Um circuito real é contado uma única vez, mesmo quando possui retorno direto, paralelo virtual ou aliases técnicos.

- `circuit_id` canônico e permanente por circuito lógico;
- consolidação automática e auditável de circuitos duplicados;
- migração de pontos, sessões, eventos e efeitos de cenas para o circuito canônico;
- prevenção de novas duplicidades ao cadastrar pontos diretos;
- contagens separadas de circuitos monitorados e pontos de acionamento;
- lista de circuitos com quantidade de pontos diretos e paralelos;
- estado desconhecido reservado a circuitos sem leitura confiável;
- diagnóstico avançado de qualidade da configuração;
- Database Schema `16`, com migração aditiva e preservação do histórico.

## LCA 0.3.4 — histórico operacional e consistência de interface

O LCA mantém o estado lógico consolidado por circuito e aproxima sua experiência visual dos demais módulos da Seiden One. A operação passa a ter períodos padronizados, paginação real, temas claro e escuro e uma hierarquia mais limpa entre estado atual, resumo, uso e histórico.

Principais recursos:

- períodos de **1 hora, 6 horas, 24 horas, 7 dias e 30 dias**;
- paginação processada pela API, com 10, 25 ou 50 ações por página;
- temas **Sistema, Claro e Escuro**, com preferência persistida no navegador;
- estado atual sem métricas redundantes, com última ação e situação de confirmação;
- contagens absolutas e percentuais nas análises de origem e uso dos pontos;
- ações confirmadas apresentadas de forma discreta e exceções destacadas;
- datas em linguagem mais natural e indicação de duração nos circuitos ligados;
- circuitos lógicos únicos preservados, sem duplicar gangs diretos e paralelos;
- informações técnicas restritas ao modo avançado;
- Database Schema 15 preservado, sem migração;
- HEA, EEA e TCA preservados.

## LCA 0.3.2 — consolidação de ações e refinamento de UX

O LCA passa a apresentar primeiro o acontecimento compreendido — luz, estado, ponto utilizado, papel do ponto, origem e confirmação — consolidando as mudanças técnicas relacionadas em uma única ação. A telemetria detalhada permanece disponível em **Informações avançadas**, voltada a implantação e troubleshooting.

Principais recursos:

- histórico principal composto por ações compreendidas, sem duplicidade visual dos efeitos técnicos;
- cards orientados ao usuário: ações compreendidas, confirmadas, sem confirmação, luzes ativas, dispositivos e itens a configurar;
- detalhes técnicos expansíveis apenas no modo avançado;
- latência de confirmação, entidades, gang, contexto do Home Assistant e evidências correlacionadas preservados para diagnóstico;
- área separada de diagnóstico técnico com mudanças brutas;
- preferência de exibição avançada salva no navegador;
- Database Schema 15 preservado, sem migração;
- HEA, EEA e TCA preservados.

## LCA 0.3.1 — atribuição da origem da interação

O LCA passa a consumir eventos explícitos publicados em `seiden/lca/interactions`, preservando o ponto que iniciou a ação. A interação é vinculada ao gang cadastrado, à luz lógica e ao papel do ponto — direto, paralelo ou cena — e pode ser correlacionada com a mudança efetiva de estado.

Principais recursos:

- diferencia acionamento local provável, usuário do Home Assistant, automação e origem desconhecida;
- mostra a posição física do interruptor que iniciou a ação;
- confirma o efeito observado e calcula o tempo entre interação e mudança de estado;
- aceita o tópico de interações mesmo quando os prefixos normais do LCA estão restritos ao Zigbee2MQTT;
- histórico com linguagem orientada ao significado: luz, estado e ponto utilizado;
- atualização do portal configurável em Manual, 1 s, 5 s, 15 s, 30 s ou 1 min;
- padrão de 15 segundos preservado e botão **Atualizar** disponível;
- Database Schema 15, exclusivamente aditivo;
- HEA, EEA e TCA preservados.

Camada de compreensão do **Seiden One**. O FLOW recebe eventos e evidências normalizadas, preserva o histórico e transforma dados operacionais em inteligência aplicada.

## LCA 0.3.0 — configuração espacial e escopo por canal

O LCA diferencia telemetria MQTT de eventos analíticos. A primeira observação estabelece o estado inicial; publicações repetidas sem mudança são mantidas apenas como telemetria técnica. Eventos e sessões são criados somente em transições reais, enquanto interações físicas explícitas permanecem registradas separadamente.

O portal do LCA agora oferece configuração visual dos dispositivos descobertos e de cada tecla. O usuário informa ambiente, posição física, ambiente adjacente, ponto de interação, direção sugerida, luz relacionada e grupo de paralelo virtual. O status do dispositivo evolui automaticamente entre Descoberto, Incompleto e Configurado, sem alterar a captura de eventos relevantes introduzida na versão 0.1.1.

## Classificação progressiva dos perfis

O Flow preserva integralmente as chaves autoritativas `optimal`, `attention` e `critical`, mas traduz seus envelopes em quatro estados operacionais:

- **Ideal:** dentro da faixa recomendada (`optimal`);
- **Atenção:** fora da faixa recomendada, mas dentro da tolerância temporária (`attention`);
- **Alerta elevado:** fora da tolerância temporária, mas ainda dentro dos limites operacionais (`critical`);
- **Crítico:** fora dos limites operacionais definidos por `critical`.

A mesma interpretação é utilizada no EEA e no TCA para temperatura e, quando aplicável, umidade. O JSON autoritativo não é alterado.

## Módulos analíticos

### HEA — Human Experience Analytics

Analisa sinais humanos agregados e anônimos produzidos pelo Seiden Vision. O portal permanece disponível em:

```text
/hea
```

### EEA — Environmental Experience Analytics

Analisa conforto e experiência ambiental para pessoas, combinando temperatura, umidade, perfis ambientais e evolução histórica.

Principais recursos:

- estado ambiental atual;
- médias, mínimos e máximos do período;
- EEA Index e distribuição das condições;
- comparação com o período anterior;
- gráficos independentes de índice, temperatura e umidade;
- filtros por local, sensor e período;
- uso dos perfis ambientais resolvidos pelo Seiden Vision.

Portal:

```text
/environment
```

### TCA — Thermal Control Analytics

Introduzido na linha 0.11.x para analisar ativos que mantêm itens em condições térmicas controladas, como geladeiras, freezers, adegas, cervejeiras e câmaras frias.

A linha atual oferece:

- cadastro genérico de ativos térmicos;
- perfis TCA carregados do `environmental_profiles.json` autoritativo;
- seleção de perfis com `analysis_type: environmental_compliance`;
- associação visual de fontes já observadas pelo Bridge;
- suporte a múltiplos sensores de temperatura e umidade;
- associação de porta, potência, tensão, corrente e energia;
- papéis por fonte, como fundo, porta, centro, produto e ambiente externo;
- fonte principal de temperatura;
- agrupamento de aberturas próximas em sessões operacionais;
- recuperação térmica geral mesmo sem sensor de porta, sem inferir causa;
- energia por episódio calculada pela integração da potência instantânea;
- interface adaptativa às capacidades disponíveis;
- visão geral para múltiplos ativos e cadastro por unidade/filial e área;
- timeline sincronizada de temperatura, porta e potência;
- catálogo persistente de fontes ainda não associadas.

Portal:

```text
/tca
```


### LCA — Lighting Context Analytics

Primeiro módulo nativo da arquitetura modular. O LCA não controla iluminação: ele interpreta eventos de acionamento e mudança de estado, descobre automaticamente dispositivos MQTT compatíveis e permite enriquecer manualmente o contexto espacial de interruptores, teclas e paralelos virtuais.

Base funcional consolidada até o LCA 0.3.0:

- descoberta automática por prefixos MQTT configuráveis;
- configuração visual de dispositivo, ambiente, posição e ambiente adjacente;
- configuração individual das teclas com progresso e status automático;
- vínculo de tecla com luz, ponto de interação e grupo de paralelo virtual;
- preservação da origem do acionamento;
- sessões de iluminação;
- métricas de eventos, interações e mudanças de estado;
- evidências de rota baseadas no contexto configurado;
- portal analítico em `/lca`;
- nenhuma função de ligar, desligar ou comandar dispositivos.

## Arquitetura

```text
Devices e sistemas
        ↓
Seiden Bridge
        ↓
Seiden Vision, quando houver enriquecimento
        ↓
Seiden FLOW
        ├── HEA
        ├── EEA
        ├── TCA
        └── LCA
```

O FLOW trabalha com eventos, capacidades e contexto. Regras analíticas não ficam presas a marcas, protocolos, tópicos MQTT ou nomes de entidades.

## Perfis ambientais e térmicos

O FLOW lê, em modo somente leitura, o arquivo mantido pelo Seiden Vision:

```text
/homeassistant/seiden_vision/environmental_profiles.json
```

Dentro do contêiner do add-on, a configuração do Home Assistant é montada em `/homeassistant`. Caso o arquivo não esteja disponível, o TCA usa perfis internos de contingência para geladeira, freezer, adega e cervejeira.

O Vision permanece como autoridade dos perfis. Customizações específicas de ativos ficam no banco do FLOW.

## Eventos consumidos

- `seiden_bridge_event`
- `seiden_connection_online`
- `seiden_connection_offline`
- `vision.analysis_completed`
- `environment.observation`

## Principais rotas

### Portais

- `/` — dashboard principal;
- `/hea` — Human Experience Analytics;
- `/environment` — Environmental Experience Analytics;
- `/tca` — Thermal Control Analytics;
- `/lca` — Lighting Context Analytics.

### APIs TCA

- `GET /api/v1/tca/profiles`
- `GET /api/v1/tca/sources`
- `GET|POST /api/v1/tca/assets`
- `GET|POST /api/v1/tca/assets/{asset_id}/bindings`
- `GET /api/v1/tca/assets/{asset_id}/analytics`
- `POST /api/v1/tca/measurements`
- `GET /api/v1/tca/dashboard`

### APIs ambientais

- `GET /api/v1/environment/sources`
- `GET /api/v1/environment/measurements`
- `GET /api/v1/environment/latest`
- `GET /api/v1/environment/summary`
- `GET /api/v1/environment/analytics`
- `GET /api/v1/environment/timeline`
- `GET /api/v1/environment/dashboard`

## Persistência e compatibilidade

- versão do FLOW: `0.15.0`;
- Platform Schema: `2.0`;
- Database Schema: `13`;
- migrações aditivas;
- ativos e associações criados na 0.11.0 são preservados;
- HEA e EEA permanecem independentes do TCA;
- dados históricos existentes não são recriados ou apagados.

## Instalação e atualização

O repositório segue o formato de add-on do Home Assistant. Após publicar os arquivos no GitHub, atualize o repositório de add-ons e instale ou atualize o **Seiden FLOW**.

Antes de substituir uma versão em produção, mantenha backup da pasta de dados do add-on. Após a atualização, valide:

1. inicialização sem erros;
2. dashboard principal;
3. `/hea`;
4. `/environment`;
5. `/tca`;
6. preservação dos dados históricos.

## Seiden One

**Every Operation Tells a Story.**  
*From events to operational intelligence.*

## Arquitetura modular — 0.12.0

A versão 0.12.0 inaugura a fundação modular do Seiden Flow sem descartar a implementação existente. HEA, EEA e TCA passam a possuir manifestos registrados em um catálogo central. O núcleo expõe os módulos carregados e as composições de solução por API, enquanto todas as rotas, bancos e dashboards da versão 0.11.7.1 permanecem compatíveis.

Estrutura inicial:

```text
app/
├── core/                 # contrato, registro e API da plataforma
├── modules/
│   ├── hea/              # Human Experience Analytics
│   ├── eea/              # Environmental Experience Analytics
│   ├── tca/              # Thermal Control Analytics
│   └── lca/              # Lighting Context Analytics 0.2.0
└── solutions/            # composições ativas e planejadas
```

Endpoints de fundação:

- `GET /api/v1/platform`
- `GET /api/v1/platform/modules`
- `GET /api/v1/platform/modules/<module_id>`
- `GET /api/v1/platform/solutions`



## LCA 0.3.0 — escopo analítico por canal

Um dispositivo pode expor vários gangs, relés ou tomadas, mas somente os canais selecionados participam da análise. Na configuração de cada tecla, desmarque **Monitorar este canal no LCA** para impedir novos eventos, sessões, métricas e evidências de rota daquele canal, preservando os demais canais e o histórico já coletado. Ao reativar, a próxima publicação estabelece uma nova linha de base e não cria uma transição artificial.

## LCA 0.2.1 — ciclo de vida de dispositivos

O LCA permite ignorar, reativar e remover dispositivos. A opção **Ignorar** é indicada quando o Bridge assina um prefixo amplo, mas um dispositivo específico não deve participar da análise. Dispositivos ignorados são descartados antes do registro de mensagens, estados, sessões ou eventos. A remoção pode preservar o histórico e, opcionalmente, bloquear uma nova descoberta.

## LCA — Home Assistant Direct Points

Flow 0.16.1 / LCA 0.4.0.3 aceita `state_transition` do HA State Driver do
Seiden Bridge.

`Home Assistant entity → Bridge HA State Driver → state_transition → LCA`

Após a primeira transição, a entidade aparece em **Infraestrutura** como fonte
Home Assistant. Configure seu ponto `Estado` como **Controla uma luz diretamente**,
defina nome e ambiente e associe normalmente os gangs Zigbee que funcionam como
paralelos virtuais.


## LCA — Canonical State Authority

A partir do LCA 0.4.0.4, o estado lógico de um circuito só pode ser alterado
por uma transição observada no ponto configurado como **direto**.

`lighting_interaction` registra intenção, origem e correlação, mas nunca grava
o estado canônico do circuito.

Essa regra vale igualmente para pontos diretos vindos do MQTT State Driver e
do HA State Driver.


## Flow 0.16.2 / LCA 0.4.1 — Time Patterns

Esta versão parte da baseline estável **Flow 0.16.1.3 / LCA 0.4.0.6** e adiciona
somente analytics temporais, sem modificar a lógica de ingestão, correlação,
pontos diretos, paralelos virtuais ou estado canônico.

O LCA passa a responder:

- quando cada circuito costuma ser utilizado;
- quanto tempo permanece ligado em cada hora do dia;
- como o uso se distribui pelos dias da semana;
- qual é a faixa típica e o horário de pico;
- como os ambientes se comparam em tempo ligado e sessões.

O heatmap e os agregados são calculados a partir das sessões lógicas já
existentes (`lca_circuit_sessions`) e respeitam o timezone operacional.


## Flow 0.16.2.1 / LCA 0.4.1.1 — UX/UI Refinement

Refinamento da visão administrativa do LCA, sem alterar a baseline analítica
ou a lógica estabilizada de pontos diretos, paralelos, MQTT State Driver e
HA State Driver.

A versão melhora hierarquia e densidade visual com:

- baseline fixa no gráfico de uso por horário;
- heatmap sequencial de intensidade com legenda;
- progressive disclosure em listas extensas;
- Top 5 na comparação entre ambientes;
- 5 ações recentes por página como padrão;
- configuração administrativa recolhida por padrão.

Toda a profundidade administrativa permanece disponível sob demanda.
