# Seiden FLOW 0.15.9.3

## LCA 0.3.9.3 — Canonical Circuit State

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