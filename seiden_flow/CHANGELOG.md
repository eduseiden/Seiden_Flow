## 0.16.3 — LCA 0.4.2 · Interaction Preference

- Adiciona **Preferências de interação** sem alterar a baseline estabilizada de ingestão, correlação, estado canônico ou sessões.
- Ranking dos pontos de acionamento mais utilizados.
- Participação de ponto direto, paralelo e cena.
- Participação de origem local, remota, automação e não identificada.
- Preferência dominante por circuito, com classificação `Uso equilibrado`, `Preferência clara` e `Preferência forte`.
- Comparação da participação de cada ponto com o período anterior de mesma duração.
- Mudanças de comportamento só são destacadas quando a variação é material (≥ 5 p.p.) e existe volume mínimo de eventos.
- Filtros independentes por ambiente e circuito.
- Analytics derivados exclusivamente de `lca_events` consolidados; nenhuma tabela nova.
- Endpoint dedicado `/api/v1/lca/interaction-preference`.
- Progressive disclosure: Top 6 pontos e Top 5 circuitos, com expansão sob demanda.
- Funções críticas de correlação preservadas byte a byte.
- README da raiz atualizado para **Seiden FLOW 0.16.3** e com resumo da release.
- DOCS e changelog atualizados.
- Schema permanece 19.

## 0.16.2.1 — LCA 0.4.1.1 · UX/UI Refinement

- Refinamento visual da tela administrativa sem alteração da lógica analítica ou de correlação.
- **Uso por horário:** baseline horizontal fixa; todas as barras partem da mesma linha e os horários ficam sempre abaixo do gráfico.
- **Heatmap semanal:** escala sequencial de seis níveis com legenda `Menor uso → Maior uso`, sem reutilizar cores de estado ou alerta.
- **Tempo de uso:** 6 circuitos por padrão, com expansão sob demanda.
- **Comparação entre ambientes:** Top 5 por padrão, microbarras comparativas e opção de expandir.
- **Ações recentes:** 5 ações por página como padrão, mantendo paginação completa.
- **Circuitos monitorados:** circuitos ligados priorizados; 6 itens por padrão e expansão sob demanda.
- **Configuração:** infraestrutura e cenas recolhidas por padrão em `Gerenciar infraestrutura e cenas`.
- Atualiza o identificador visual do rodapé para LCA 0.4.1.1.
- Backend `repository.py` preservado byte a byte em relação ao Flow 0.16.2 / LCA 0.4.1.
- README da raiz, DOCS e changelog atualizados.
- Schema permanece 19.

## 0.16.2 — LCA 0.4.1 · Time Patterns

- Adiciona **Padrões de uso** sem alterar a baseline lógica congelada da LCA 0.4.0.6.
- Uso por hora do dia calculado por **tempo efetivamente ligado**, não por quantidade de acionamentos.
- Sessões que atravessam horas são distribuídas corretamente entre cada faixa horária.
- Uso por dia da semana com tempo ligado, sessões e participação no período.
- Heatmap semanal `dia × hora`, calculado no timezone operacional configurado.
- Calcula faixa típica de uso como a menor janela horária circular que concentra pelo menos 70% do tempo ligado.
- Identifica horário de pico e participação de dias úteis, finais de semana e período noturno.
- Comparação entre ambientes: tempo ligado, sessões, duração média, maior sessão e circuitos utilizados.
- Filtros independentes por ambiente e circuito.
- Analytics derivados exclusivamente de `lca_circuit_sessions`; nenhuma nova tabela ou alteração de schema.
- Endpoint dedicado `/api/v1/lca/time-patterns` para evitar acoplar o cálculo ao dashboard principal.
- Mantém schema de banco 19.
- README da raiz e documentação do add-on atualizados.

## 0.16.1.3 — LCA 0.4.0.6 · Interaction Baseline Restore

- Restaura integralmente a semântica de `lighting_interaction` comprovada na LCA 0.3.9.3.
- Mantém as evoluções atuais de sessões, MQTT State Driver e HA State Driver.
- Corrige detecção de paralelo considerando `light_asset_id` **ou** `related_light_id`.
- Impede que `state_transition` crie uma segunda ação quando o circuito possui paralelo virtual.
- Adiciona supressão analítica de ecos de sincronização: para o mesmo circuito e mesmo estado solicitado, a primeira interação é preservada e mudanças subsequentes de outros pontos dentro da janela causal de 4,5 s não viram novas ações.
- As mensagens MQTT brutas continuam preservadas em `lca_messages`; apenas a duplicação analítica é descartada.
- Não altera HTML/CSS/UX do LCA 0.4.0.5.
- Mantém `0 execuções`, `1 execução`, `2 execuções`.
- Schema de banco permanece 19.

## 0.16.1.2 — LCA 0.4.0.5 · Direct/Parallel Regression Fix

- Compara e restaura a semântica comprovada da LCA 0.3.9.3 para circuitos com paralelo virtual.
- **Sem paralelo:** `state_transition` do ponto direto atualiza o estado e gera uma única ação com origem desconhecida.
- **Com paralelo:** `lighting_interaction` mantém a origem/intenção; a transição do ponto direto confirma o efeito; a interação confirmada atualiza o estado lógico.
- A regra é idêntica para ponto direto MQTT/Zigbee2MQTT e ponto direto Home Assistant.
- Remove a criação prematura de ação direta sintética em circuitos com paralelo.
- Corrige a resolução pendente para preservar a identidade real do paralelo sempre que `source_device/source_channel` permitirem.
- Remove a reconciliação 0.4.0.4 que conflitava com a semântica de circuitos com paralelo.
- Mantém Cenas: `0 execuções`, `1 execução`, `2 execuções`.
- Schema permanece 19.

## 0.16.1.1 — LCA 0.4.0.4 · Canonical State Authority Fix

- Corrige regressão em que `lighting_interaction` podia alterar `lca_circuit_state`.
- Reforça a invariável: **interação = intenção/origem; transição do ponto direto = estado real**.
- `lighting_interaction` nunca mais grava estado canônico do circuito.
- A confirmação de uma interação continua correlacionando intenção e efeito, mas não altera estado.
- Adiciona reconciliação única na atualização para reparar estados atuais usando apenas o último estado do ponto direto configurado.
- Preserva sessões históricas fechadas e reconcilia somente a sessão atualmente aberta.
- Mantém suporte a MQTT State Driver e HA State Driver.
- Mantém banco no schema 19.
- Confirma correção de português em Cenas: `0 execuções`, `1 execução`, `2 execuções`.

## 0.16.1 — LCA 0.4.0.3 · Home Assistant Direct Points

- LCA passa a consumir `state_transition` do **HA State Driver** do Seiden Bridge 0.15.x.
- Entidades HA monitoradas pelo Bridge são descobertas como fontes de estado com canal lógico `main`.
- Uma fonte HA pode ser configurada como **ponto direto** de um circuito.
- O ponto direto segue como fonte canônica do estado; paralelos virtuais continuam chegando por `seiden/lca/interactions`.
- Mantém correlação entre intenção do paralelo e mudança do ponto direto, sem dupla contagem.
- O LCA não consulta o Home Assistant diretamente: continua consumindo somente eventos normalizados do Bridge.
- UI identifica fontes Home Assistant e apresenta `Estado` no lugar do canal técnico `main`.
- Corrige `execução` / `execuções` na seção Cenas.
- Sem alteração de banco: schema permanece 19.

## 0.16.0.2 — LCA 0.4.0.2: Circuit Usage UX Refinement

- Corrige pluralização de `sessão/sessões` na utilização por circuito.
- Por padrão, a seção **Tempo de uso** mostra apenas circuitos que tiveram uso no período selecionado.
- Adiciona filtro por local sem alterar o período global do dashboard.
- Adiciona opção discreta **Mostrar sem uso**, desativada por padrão.
- KPIs de utilização passam a respeitar o local selecionado e continuam calculados apenas sobre circuitos efetivamente usados.
- Ordenação padrão permanece por maior tempo ligado, reduzindo poluição visual em instalações com muitos circuitos.
- Refino responsivo e de contraste dos novos filtros em dark mode.
- Sem alteração de schema; `DATABASE_SCHEMA_VERSION = 19`.

## 0.16.0 — LCA 0.4.0: Circuit Usage Analytics

- Adiciona `lca_circuit_sessions`, sessão canônica por circuito lógico.
- Sessões são abertas/fechadas apenas por transições do estado canônico, evitando duplicidade por pontos paralelos ou telemetria repetida.
- Migra histórico confirmado existente para sessões de uso (`lca_circuit_usage_sessions_040`).
- Dashboard passa a expor tempo ligado, sessões, duração média, maior sessão e percentual de utilização por circuito.
- Nova seção “Tempo de uso” com hierarquia visual coerente com a LCA 0.3.9, responsiva e revisada para dark mode.
- Mantém sem alterações o histórico operacional, a configuração por dispositivo MQTT + L1/L2/L3 e a fonte única de verdade de estado introduzida na 0.3.9.3.
- `DATABASE_SCHEMA_VERSION = 19`.

## 0.15.9.3 — LCA 0.3.9.3: Canonical Circuit State

- Introduz estado canônico persistente por circuito em `lca_circuit_state`.
- Deixa de inferir o estado atual da carga a partir do estado técnico de pontos diretos ou paralelos.
- Interações confirmadas atualizam o circuito pelo `requested_state`, inclusive em paralelos.
- Migração inicializa circuitos existentes pela última interação confirmada, com fallback seguro para a última telemetria disponível.
- Cabeçalho e **Circuitos monitorados** passam a consumir a mesma fonte de verdade.
- Protege contra eventos fora de ordem sobrescrevendo estado mais recente.
- Mantém integralmente UX/UI, dark mode e identidade MQTT da LCA 0.3.9.
- Database Schema atualizado para 18.

## 0.15.9.2 — LCA 0.3.9.2

- Corrige regressão de estado lógico introduzida na 0.15.9.1.
- Restaura a regra comprovada da 0.15.7: o estado consolidado do circuito usa a evidência válida mais recente entre seus pontos associados, sem priorizar artificialmente pontos diretos.
- Mantém integralmente os refinamentos visuais, dark mode e identidade MQTT da 0.15.9.x.

## 0.15.9.1 — LCA 0.3.9.1: Logical State Regression Fix

- Corrige regressão do estado consolidado dos circuitos no dashboard.
- Pontos diretos passam a ser a fonte preferencial do estado lógico do circuito.
- Pontos paralelos continuam contribuindo para ações e métricas, mas não sobrescrevem o estado real quando existe um ponto direto monitorado.
- Cabeçalho e lista de Circuitos monitorados voltam a usar a mesma fonte canônica de estado.
- Mantidos os refinamentos de UX/UI e dark mode da 0.15.9.

## 0.15.9 — LCA 0.3.9: Visual Language & Dark Mode Refinement

- Simplifica **Circuitos monitorados** para priorizar nome, ambiente e quantidade de pontos de acionamento.
- Move a composição direto/paralelo e a última mudança para **Informações avançadas**, reduzindo densidade visual.
- Unifica o estado de circuitos e histórico com a mesma linguagem visual: âmbar para ligado e cinza neutro para desligado.
- Adiciona legenda discreta de estado também em **Circuitos monitorados**, sem repetir badges textuais em cada item.
- Reserva o âmbar para iluminação/estado ativo; gráficos de origem e papel passam a usar azul, roxo e tons neutros.
- Corrige pluralização de tecla/teclas e execução/execuções.
- Revisa contraste do modo escuro em subtítulos, metadados, campos, botões, legendas, divisores e estados.
- Mantém toda a lógica analítica, schema 17 e identidade MQTT do LCA 0.3.7 intactos.

## 0.15.8 — LCA 0.3.8: Operational History UX

- Reforça a hierarquia visual da seção **Ações recentes** com cabeçalho próprio e descrição objetiva.
- Remove a repetição textual “ligada/desligada” do título de cada ocorrência.
- Introduz estado visual por ponto: âmbar para ligado e cinza neutro para desligado.
- Adiciona legenda discreta no rodapé da lista, preservando vermelho apenas para exceções e alertas.
- Melhora espaçamento, alinhamento, hover e responsividade da lista de ações em temas claro e escuro.
- Mantém detalhes técnicos e “Sem confirmação” apenas quando aplicáveis, sem alterar a lógica analítica do LCA 0.3.7.

## 0.15.7 — LCA 0.3.7: MQTT Infrastructure Identity

- define a infraestrutura do LCA pelo dispositivo/tópico Zigbee2MQTT e pelos canais canônicos L1/L2/L3/...;
- impede que `source_entity` e nomes amigáveis de gangs criem dispositivos sintéticos;
- correlaciona interações renomeadas pela transição real do canal MQTT e pelo `circuit_id`;
- adiciona fila curta para interações que chegam antes da mudança de estado;
- oculta automaticamente aliases sintéticos antigos sem evidência de estado real;
- mantém `source_entity` somente como metadado técnico para diagnóstico;
- atualiza Database Schema para 17 e preserva HEA, EEA, TCA, circuitos e histórico válido.

## 0.15.6 — LCA 0.3.6: Logical Circuit Consolidation

- introduz `circuit_id` canônico para circuitos de iluminação;
- consolida duplicidades por nome e ambiente, incluindo registros antigos sem ambiente quando há um único destino inequívoco;
- migra pontos, sessões, eventos e efeitos de cenas para o circuito canônico, com log de auditoria;
- evita novas duplicidades ao cadastrar pontos diretos;
- separa contagens de circuitos e pontos de acionamento;
- mostra pontos diretos e paralelos por circuito;
- adiciona diagnóstico avançado de qualidade da configuração;
- atualiza Database Schema para 16, preservando HEA, EEA, TCA e todo o histórico.

## 0.15.5 — LCA 0.3.5: Identity Resolution & Physical Channel Normalization

- Corrige falsos `Sem confirmação` em pontos diretos com nomes livres.
- Resolve a origem por circuito lógico e destino, sem depender de convenções de nome.
- Confirma pontos diretos pela própria transição observada.
- Consolida aliases `l1/left`, `l2/center` e `l3/right` em três teclas físicas.
- Migra configuração, estado e histórico dos aliases existentes.
- Mantém Database Schema 15 e preserva HEA, EEA e TCA.

## 0.15.4 — LCA 0.3.4: Operational History & Interface Consistency

- adiciona períodos de 1 hora, 6 horas, 24 horas, 7 dias e 30 dias;
- implementa paginação real das ações pela API, com 10, 25 ou 50 registros por página;
- inclui temas Sistema, Claro e Escuro, com preferência persistida;
- remove redundâncias do Estado atual e destaca a última ação;
- mostra contagens absolutas e percentuais nas distribuições;
- simplifica ações confirmadas e destaca apenas exceções;
- adota datas mais humanas e melhora a apresentação dos circuitos ativos;
- mantém informações técnicas restritas ao modo avançado;
- preserva Database Schema 15 e os módulos HEA, EEA e TCA.

## 0.15.3 — LCA 0.3.3: Logical State & Experience Redesign

- Corrige o indicador de luzes ativas para contar circuitos lógicos únicos.
- Consolida o estado atual por `light_asset_id`, deduplicando pontos diretos e paralelos.
- Adiciona `current_lights`, `active_lights`, `monitored_lights` e `unknown_lights` à API do dashboard.
- Adiciona distribuições de origem e papel dos pontos no período.
- Redesenha o portal segundo a identidade visual Seiden One, com assinatura âmbar do LCA.
- Oculta nomes de tecnologias internas da visão padrão; dados técnicos permanecem no modo avançado.
- Reorganiza o painel em Estado atual, Resumo, Uso da iluminação, Operação e Configuração.
- Mantém Database Schema 15 e preserva HEA, EEA e TCA.

## 0.15.2 — LCA 0.3.2: Event Consolidation & UX Refinement

- Consolida interação e efeitos técnicos em uma única ação compreensível no histórico principal.
- Reformula os indicadores para ações compreendidas, confirmadas, sem confirmação, luzes ativas, dispositivos e itens a configurar.
- Introduz opção **Informações avançadas**, desativada por padrão e persistida no navegador.
- Mantém latência, entidades, contexto do Home Assistant e evidências técnicas em detalhes expansíveis.
- Separa diagnóstico técnico da visão operacional.
- Amplia `/api/v1/lca/dashboard` com `recent_actions`, `technical_events`, `confirmed_interactions` e `unconfirmed_interactions`, preservando compatibilidade.
- Mantém Database Schema 15; nenhuma migração. HEA, EEA e TCA preservados.

# Changelog

## 0.15.1 — LCA 0.3.1: Interaction Origin Attribution

- ingere eventos explícitos em `seiden/lca/interactions`;
- resolve a origem para o dispositivo e gang já cadastrados, sem criar duplicatas por diferença de caixa;
- registra modo de origem, entidade fonte, contexto do Home Assistant, circuito e alvo;
- vincula a interação à luz lógica e identifica ponto direto, paralelo ou cena;
- correlaciona interação e mudança de estado, registrando confirmação e latência;
- aceita o tópico canônico independentemente dos prefixos Zigbee2MQTT configurados;
- apresenta eventos recentes em linguagem orientada à luz e ao ponto utilizado;
- inclui refresh Manual, 1 s, 5 s, 15 s, 30 s e 1 min, com preferência local e botão Atualizar;
- Database Schema 15, apenas aditivo; HEA, EEA e TCA preservados.

## 0.15.0 — LCA 0.3.0: Lighting Relationship Model

- gangs classificados como retorno direto, paralelo, cena ou ignorado;
- pontos reais formam um catálogo reutilizável para associação por combobox;
- paralelos herdam automaticamente luz e ambiente do ponto real;
- cenas possuem nome, descrição e aprendizado estatístico explicável;
- efeitos observados até 3 segundos após uma cena são agrupados causalmente;
- eventos causados por cena não são tratados como evidências independentes de rota;
- Database Schema 14, somente aditivo; HEA, EEA e TCA preservados.

# Changelog

## 0.15.0 — LCA 0.3.0: Simplified Configuration Experience

- reorganiza a configuração em localização do interruptor e seleção das teclas;
- substitui formulários extensos por uma lista compacta de canais;
- mantém campos de circulação e contexto avançado recolhidos por padrão;
- herda o ambiente do dispositivo para as teclas;
- remove da interface a seleção manual de situação/status;
- considera uma tecla básica configurada quando possui nome ou função relacionada;
- mantém paralelos virtuais e evidências de circulação como configuração opcional;
- preserva Database Schema 13 e toda a lógica de ingestão do LCA 0.2.2;
- não altera HEA, EEA ou TCA.

## 0.14.2 — LCA 0.2.2: Channel Scope Management

- permite ativar ou desativar individualmente `state_l1`, `center` e demais canais descobertos;
- canais desativados deixam de gerar mensagens armazenadas, baseline, mudanças, interações, sessões, métricas e evidências de rota;
- os demais canais do mesmo dispositivo continuam sendo processados normalmente;
- dashboard e APIs ocultam, por padrão, o histórico de canais atualmente desativados, sem apagá-lo;
- reativação cria uma nova linha de base para evitar transição artificial;
- sessões abertas de um canal são removidas ao alterar seu escopo;
- status do dispositivo passa a considerar somente os canais monitorados;
- portal exibe contagem de canais monitorados e ignorados;
- HEA, EEA e TCA permanecem inalterados;
- Database Schema permanece em `13`.

## 0.14.1 — LCA 0.2.1: Device Lifecycle Management

- permite ignorar dispositivos e descartar novos eventos antes de qualquer processamento analítico;
- adiciona lista de dispositivos ignorados e reativação;
- adiciona remoção com opção de preservar ou apagar histórico;
- permite bloquear nova descoberta quando a assinatura MQTT por prefixo continuar ativa;
- exclui ignorados dos contadores, rankings e eventos recentes;
- adiciona os endpoints de ciclo de vida do dispositivo;
- atualiza o Database Schema para 13 por meio de tabela aditiva de exclusões;
- mantém HEA, EEA e TCA sem alterações funcionais.

## 0.14.0 — LCA 0.2.0: Device and Spatial Configuration

- adiciona configuração visual dos dispositivos descobertos diretamente no portal LCA;
- permite informar nome amigável, tipo, ambiente, posição física, ambiente adjacente e observações;
- adiciona configuração individual de cada tecla/canal;
- permite registrar ponto de interação, direção sugerida, luz ou função relacionada e grupo de paralelo virtual;
- calcula automaticamente o progresso de configuração de cada dispositivo;
- introduz estados `discovered`, `incomplete`, `configured` e `ignored`;
- mantém a captura de eventos relevantes e o polling de 15 segundos;
- não adiciona comandos de iluminação e não altera HEA, EEA ou TCA;
- mantém o Database Schema 12.

## 0.13.1 — LCA 0.1.1: Relevant Event Processing

- diferencia mensagens MQTT, mudanças reais de estado e interações explícitas;
- trata a primeira leitura de cada canal apenas como estado inicial;
- ignora publicações periódicas sem alteração de valor no histórico analítico;
- cria sessões somente em transições `OFF → ON` e encerra em `ON → OFF`;
- adiciona estado persistente por dispositivo e canal;
- adiciona contador técnico de mensagens recebidas, separado dos eventos relevantes;
- aplica janela antirrepetição de dois segundos para ações idênticas;
- remove uma única vez os eventos de estado e sessões sintéticas gerados pelo LCA 0.1.0, preservando interações e disponibilidade;
- mantém o Database Schema 12 com tabelas aditivas internas ao módulo;
- preserva HEA, EEA e TCA sem alterações funcionais.

## 0.13.0.1 — Correção de navegação do LCA

- adiciona o card e o link do LCA à página inicial do Flow;
- corrige os links TCA e LCA para respeitar o ingress path;
- mantém HEA, EEA, TCA e todas as APIs sem alteração funcional.

## 0.13.0 — LCA 0.1.0

- Introduz o **LCA — Lighting Context Analytics**, primeiro módulo desenvolvido nativamente sobre a arquitetura modular.
- O LCA compreende eventos de iluminação e não envia comandos a dispositivos.
- Adiciona descoberta automática de dispositivos MQTT por prefixos configuráveis.
- Preserva dispositivo, canal/tecla, ação, estado, brilho, tópico e horário.
- Adiciona enriquecimento manual de localização, posição, ambiente adjacente, direção provável, luz relacionada e grupo de paralelo virtual.
- Cria sessões liga/desliga e indicadores de atividade.
- Introduz evidências de rota, sempre apresentadas como sinais contextuais e não como localização confirmada de pessoas.
- Adiciona portal `/lca` e APIs `/api/v1/lca`.
- Incrementa o Database Schema para `12` com migração exclusivamente aditiva.
- Preserva HEA, EEA e TCA sem alterações funcionais.

## 0.12.0 — Modular Foundation

- Introduz o registro central de módulos do Seiden Flow.
- Formaliza um contrato comum de manifesto para módulos analíticos.
- Registra HEA, EEA e TCA como módulos reutilizáveis, preservando integralmente suas rotas e comportamentos atuais.
- Padroniza o nome TCA como **Thermal Control Analytics**.
- Adiciona catálogo de capacidades, eventos consumidos, dependências, portais e prefixos de API por módulo.
- Adiciona os endpoints `/api/v1/platform`, `/api/v1/platform/modules`, `/api/v1/platform/modules/<module_id>` e `/api/v1/platform/solutions`.
- Introduz o primeiro catálogo de composições, distinguindo claramente soluções ativas de soluções planejadas.
- O endpoint de health passa a informar a arquitetura e os módulos carregados.
- Mantém `DATABASE_SCHEMA_VERSION = 11`; não altera dados, perfis, analytics, dashboards ou integrações existentes.
- Estabelece a fundação para que novos módulos sejam adicionados sem ampliar o monólito atual.

## 0.11.7.1

- Corrige a régua térmica do TCA para usar uma única escala numérica proporcional.
- Faixas coloridas agora respeitam a largura real de cada intervalo em graus.
- Limites da escala passam a ser posicionados exatamente sobre seus valores.
- A leitura atual é exibida sobre o marcador, mantendo o valor visível sem interação.
- As extremidades internas da régua representam corretamente “Alerta elevado”; o estado crítico permanece reservado a valores fora dos limites operacionais.
- Não altera perfis, classificação, banco de dados, APIs ou análise de recuperação.

## 0.11.7

- Sessões de acesso agrupadas em janela de 90 segundos.
- Novo estado “Recuperação não concluída”, reduzindo falsos casos de interrupção.
- Paginação da tabela de sessões (10/25/50) e filtros por status.
- Eixos X/Y, grades e tooltips nos gráficos sincronizados.
- Detalhe de sessão sob demanda.
- Sensores conectados recolhidos por padrão.
- Resumo de recuperação mais objetivo.

## 0.11.6.2

- Simplifica a apresentação das faixas no EEA e no TCA.
- EEA usa linguagem de conforto para perfis humanos e linguagem técnica para os demais perfis.
- Faixas aninhadas passam a ser exibidas como zonas reais, recolhidas em detalhes.
- Estado atual e posição na faixa ganham prioridade visual.

## 0.11.6.1

- Corrige falha 500 nas APIs do TCA causada pela ausência da importação do classificador compartilhado em `tca_analytics.py`.
- Mantém inalterada a classificação progressiva de quatro estados no EEA e no TCA.
- Não altera banco de dados, schemas ou configuração dos ativos.

## 0.11.6

- Cria um classificador compartilhado de perfis ambientais para EEA e TCA.
- Preserva as chaves autoritativas `optimal`, `attention` e `critical` sem alterar o JSON do Vision.
- Traduz os três envelopes em quatro estados: Ideal, Atenção, Alerta elevado e Crítico.
- Define `critical` como limite operacional externo; a condição crítica ocorre fora desses limites.
- Adiciona direção da ocorrência: abaixo ou acima das faixas e limites.
- Valida a ordem e a integridade dos envelopes antes de classificar.
- EEA passa a mostrar a classificação progressiva individual de temperatura e umidade, com linguagem de faixa recomendada, tolerância temporária e limites operacionais.
- TCA passa a usar a mesma classificação progressiva no estado térmico e na visão consolidada.
- Adiciona régua visual de sete zonas e marcador da leitura atual no perfil TCA.
- Mantém HEA, schemas e banco de dados sem alteração.

## 0.11.5.1

- Corrige a abertura do editor em lote de sensores.
- Amplia o filtro TCA para 1h, 6h, 12h, 24h, 7d e 30d.

# Changelog

## 0.11.5.1

- TCA adaptativo por capacidades: a interface exibe apenas análises compatíveis com os sensores conectados.
- Recuperação térmica geral sem sensor de porta, com causa explicitamente não identificada.
- Aberturas próximas passam a ser agrupadas em sessões operacionais.
- Energia por episódio calculada pela integração trapezoidal da potência instantânea; o acumulado Tuya não é usado em episódios curtos.
- Classificação contextual: faixa de atenção em retorno ao ideal é apresentada como recuperação normal.
- Timeline vertical sincronizada de temperatura, porta e potência, ajustada ao intervalo real com dados.
- Visão geral dos ativos para operações com múltiplas geladeiras, freezers e outros ativos térmicos.
- Cadastro preparado para unidade/filial e área, persistidos como metadados do ativo.
- Rodapé com assinatura visual Seiden One e refinamento do espaçamento do cabeçalho.
- TCA interno evoluído para 0.2, sem AI e sem manutenção preditiva.

## 0.11.3

- Corrige o botão **Cancelar** do cadastro de ativo TCA, que era bloqueado pela validação HTML do campo obrigatório.
- Corrige o botão **Fechar** da associação de sensores pelo mesmo motivo.
- Os dois controles agora são botões explícitos de interface e fecham seus respectivos diálogos sem submeter formulários.

## 0.11.3

- Cataloga eventos MQTT genéricos usando identidade estável derivada de conexão e tópico.
- Reconhece payloads TCA aninhados em `data`, incluindo potência, corrente, tensão e energia acumulada.
- Reconhece sensores Zigbee2MQTT de porta pelo campo `contact`, respeitando `true = fechada` e `false = aberta`.
- Exige campos elétricos canônicos com unidade (`power_w`, `voltage_v`, `current_a`, `energy_total_kwh`), evitando confundir tensão de bateria Zigbee com tensão da alimentação do ativo.
- Limpa automaticamente capacidades, vínculos e medições de tensão incorretas criadas por versões anteriores.
- Mantém HEA e EEA sem alterações funcionais.

# 0.11.1

- Cadastro TCA orientado por perfis e capacidades, sem digitação obrigatória de Source ID.
- Perfis `environmental_compliance` lidos do arquivo autoritativo do Seiden Vision, com fallback interno.
- Catálogo persistente de fontes observadas e associação visual de múltiplas métricas.
- Manifesto corrigido para `version: 0.11.1`.
- Montagem `homeassistant_config` adicionada em modo somente leitura para acesso aos perfis do Vision.
- README e documentação técnica atualizados para HEA, EEA e TCA.
- Compatibilidade preservada com ativos e bindings da 0.11.0.

## 0.11.0

- Introduz o Thermal Control Analytics (TCA 0.1).
- Cadastro genérico de ativos térmicos e associação dinâmica de fontes.
- Suporte a múltiplos sensores de temperatura, umidade opcional, portas e métricas elétricas.
- Episódios de abertura, impacto térmico, recuperação e energia estimada.
- Novo portal `/tca` e API `/api/v1/tca`.
- Nenhum acoplamento a fabricante, protocolo ou entidade específica.

## 0.10.3.1

- Move a identidade visual da Seiden One do cabeçalho para o rodapé.
- Mantém o texto “Powered by Seiden One Intelligence” à esquerda e posiciona o logo à direita.
- Melhora o equilíbrio visual do cabeçalho sem alterar funcionalidades, dados ou estrutura de publicação.

## 0.10.3

- Reposiciona o filtro de período junto ao resumo histórico do EEA.
- Mantém Local e Sensor como filtros globais no topo da página.
- Exibe o intervalo efetivamente analisado.
- Inclui identidade visual discreta da Seiden One no cabeçalho.
- Preserva a estrutura, o schema e a compatibilidade de publicação da versão anterior.

# Changelog

## 0.10.2

- Hotfix: restaura `SCHEMA_VERSION = "2.0"` e `DATABASE_SCHEMA_VERSION = 9` em `app/version.py`.
- Corrige a falha de boot do Gunicorn causada por `ImportError` na inicialização.
- Mantém integralmente os ajustes de UX/UI da versão 0.10.1.
- Nenhuma alteração no schema do banco de dados ou na estrutura de publicação.

## 0.10.1

- Reorganiza o EEA para apresentar **Estado atual** no início da visão detalhada.
- Mantém a leitura instantânea e suas faixas antes da análise histórica.
- Substitui o gráfico combinado por três cards independentes: EEA Index, temperatura e umidade.
- Aplica escala e unidade próprias a cada gráfico, eliminando sobreposição e ambiguidade visual.
- Exibe a média do período no cabeçalho de cada gráfico.
- Adapta os três gráficos para uma coluna em telas menores.
- Oculta o gráfico de umidade quando o perfil não avalia essa métrica.
- Preserva estrutura do add-on, banco, endpoints e compatibilidade de publicação.

## 0.10.0

- EEA evolui de fotografia instantânea para **Environmental Experience Analytics** histórico.
- Mantém o bloco de estado atual e adiciona resumo real do período selecionado.
- Exibe EEA médio, mínimo e máximo no período.
- Exibe temperatura e umidade médias, mínimas e máximas.
- Exibe cobertura, quantidade de amostras e comparação determinística com o período anterior.
- Adiciona evolução temporal de temperatura, umidade e EEA Index.
- Adiciona distribuição percentual por faixa de experiência ambiental.
- O endpoint `/api/v1/environment/analytics` passa a incluir a timeline de forma aditiva e retrocompatível.
- Nenhuma alteração na estrutura do add-on, no banco de dados ou no formato de publicação.

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
