# Seiden FLOW 0.13.0.1

Camada de compreensão do **Seiden One**. O FLOW recebe eventos e evidências normalizadas, preserva o histórico e transforma dados operacionais em análises para pessoas, ambientes e ativos térmicos.


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

Recursos da versão 0.1.0:

- descoberta automática por prefixos MQTT configuráveis;
- cadastro assistido de dispositivo, canal, localização, posição e ambiente adjacente;
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

- versão do FLOW: `0.13.0.1`;
- Platform Schema: `2.0`;
- Database Schema: `12`;
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


### LCA — Lighting Context Analytics

Primeiro módulo nativo da arquitetura modular. O LCA não controla iluminação: ele interpreta eventos de acionamento e mudança de estado, descobre automaticamente dispositivos MQTT compatíveis e permite enriquecer manualmente o contexto espacial de interruptores, teclas e paralelos virtuais.

Recursos da versão 0.1.0:

- descoberta automática por prefixos MQTT configuráveis;
- cadastro assistido de dispositivo, canal, localização, posição e ambiente adjacente;
- vínculo de tecla com luz, ponto de interação e grupo de paralelo virtual;
- preservação da origem do acionamento;
- sessões de iluminação;
- métricas de eventos, interações e mudanças de estado;
- evidências de rota baseadas no contexto configurado;
- portal analítico em `/lca`;
- nenhuma função de ligar, desligar ou comandar dispositivos.

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
│   └── lca/              # Lighting Context Analytics 0.1.0
└── solutions/            # composições ativas e planejadas
```

Endpoints de fundação:

- `GET /api/v1/platform`
- `GET /api/v1/platform/modules`
- `GET /api/v1/platform/modules/<module_id>`
- `GET /api/v1/platform/solutions`

