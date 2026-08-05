# Seiden FLOW 0.14.1 — Documentação técnica

## Identificação

- Serviço: `seiden_flow`
- Versão: `0.14.1`
- Platform Schema: `2.0`
- Database Schema: `13`
- Porta interna: `8100`
- Persistência: SQLite na pasta de configuração do add-on

## Responsabilidade do FLOW

O FLOW é a camada de entendimento operacional do Seiden One. Ele recebe eventos normalizados, preserva medições, agrega períodos, correlaciona fontes e expõe portais e APIs analíticas.

O módulo não deve depender de marcas ou devices específicos. A origem pode ser MQTT, Home Assistant, APIs, bancos ou outras conexões do Bridge.


## Classificador compartilhado de perfis

O módulo `profile_classification.py` centraliza a interpretação dos envelopes ambientais para EEA e TCA. Ele não altera o contrato do Vision nem o `environmental_profiles.json`.

Semântica:

- `optimal`: faixa recomendada;
- `attention`: envelope de tolerância temporária;
- `critical`: limites operacionais externos;
- valor fora de `critical`: condição crítica.

Estados derivados: `ideal`, `attention`, `elevated_alert` e `critical`.

O classificador também valida a ordem:

```text
critical.min <= attention.min <= optimal.min <= optimal.max <= attention.max <= critical.max
```

Perfis incompletos ou fora dessa ordem são marcados como inválidos, sem classificação silenciosa.

## HEA

O Human Experience Analytics consome evidências humanas agregadas e mantém o portal `/hea`. A linha 0.11.x não altera o motor HEA.

## EEA

O Environmental Experience Analytics analisa ambientes voltados a pessoas. O portal `/environment` separa:

- estado atual;
- resumo do período;
- evolução de EEA Index, temperatura e umidade;
- distribuição das condições;
- filtros de local, fonte e período.

O EEA preserva medições ambientais e usa os campos enriquecidos pelo Vision, incluindo perfil, faixas aplicadas, pontuações, condições e motivos.

## TCA 0.2

O Thermal Control Analytics analisa ativos térmicos.

### Ativos

Cada ativo possui:

- `asset_id`;
- nome;
- tipo e perfil;
- faixa ótima derivada do perfil;
- avaliação opcional de umidade;
- metadados e snapshot do perfil aplicado.

### Perfis

O catálogo principal é lido de:

```text
/homeassistant/seiden_vision/environmental_profiles.json
```

Somente perfis com `analysis_type = environmental_compliance` são apresentados no TCA. O arquivo é somente leitura para o FLOW. Há fallback interno caso a configuração autoritativa esteja indisponível.

### Fontes e bindings

As fontes observadas pelo Bridge são catalogadas antes da associação. Um ativo pode ter múltiplas fontes e múltiplas métricas por fonte:

- `temperature`;
- `humidity`;
- `door`;
- `power`;
- `voltage`;
- `current`;
- `energy`.

Cada binding pode declarar um papel operacional e a referência principal de temperatura.

### Episódios

O motor TCA correlaciona eventos de abertura, medições térmicas e potência para produzir sessões com duração, impacto, recuperação e energia integrada. Sem sensor de porta, identifica excursões térmicas e recuperação sem atribuir causalidade. A interface é adaptativa às capacidades disponíveis e o cadastro aceita unidade/filial e área para preparar operações distribuídas. A linha 0.11.x ainda não afirma diagnóstico de falha nem manutenção preditiva por AI.

## Montagens do add-on

O manifesto monta:

- `addon_config` com escrita, para banco e configurações próprias;
- `homeassistant_config` em modo somente leitura, para consumir os perfis mantidos pelo Vision.

## Compatibilidade

A migração para Database Schema 12 é aditiva. Tabelas e dados anteriores são preservados. HEA e EEA continuam disponíveis mesmo sem ativos TCA cadastrados.

## Modular Foundation (0.12.0)

A fundação modular usa `ModuleManifest` e `ModuleRegistry` para declarar e descobrir capacidades analíticas. A versão 0.12.0 não migrou o banco nem alterou contratos existentes: ela cria a fronteira arquitetural que permitirá extrair gradualmente rotas, repositórios, analytics e interfaces de cada módulo.

Cada manifesto declara: identificador, nome, versão interna, estado, eventos consumidos, capacidades, portais, prefixos de API e dependências. Novos módulos devem ser registrados em `app/modules/catalog.py`.

O catálogo de soluções diferencia composições `active` e `planned`; uma composição planejada não significa que seus módulos estejam implementados.


## LCA 0.1.0

O Lighting Context Analytics consome eventos normalizados pelo Bridge, descobre dispositivos sob os prefixos MQTT configurados e cria contexto analítico de iluminação. Não possui APIs de comando. Portal: `/lca`. Prefixo de API: `/api/v1/lca`.

## LCA 0.2.1 — configuração espacial assistida

- portal com edição de dispositivo e teclas;
- enriquecimento de ambiente, posição, adjacência e direção;
- vínculo com luz/função e grupos de paralelo virtual;
- status automático `discovered`, `incomplete` e `configured`;
- opção explícita para ignorar dispositivos sem relevância analítica;
- nenhuma função de comando ou controle de iluminação.

O LCA mantém o último estado observado de cada canal. A primeira publicação estabelece a linha de base e não gera evento. Publicações seguintes com o mesmo valor contam apenas como mensagens técnicas. Uma mudança real gera `state_change`; ações explícitas do dispositivo geram `interaction`. Sessões são abertas e fechadas somente por transições reais.

## LCA 0.2.1 — ciclo de vida de dispositivos

O LCA permite ignorar, reativar e remover dispositivos. A opção **Ignorar** é indicada quando o Bridge assina um prefixo amplo, mas um dispositivo específico não deve participar da análise. Dispositivos ignorados são descartados antes do registro de mensagens, estados, sessões ou eventos. A remoção pode preservar o histórico e, opcionalmente, bloquear uma nova descoberta.

### Ciclo de vida de dispositivos LCA

- `GET /api/v1/lca/devices/ignored`
- `POST /api/v1/lca/devices/{device_id}/reactivate`
- `DELETE /api/v1/lca/devices/{device_id}`

O `DELETE` aceita `preserve_history` e `ignore_future` no corpo JSON.
