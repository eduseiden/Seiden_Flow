# Changelog

## 0.4.0

- Portal web externo do Human Experience Analytics em `/hea`.
- API pública sanitizada em `/api/v1/public/hea/dashboard`.
- Visual responsivo para desktop, tablet e celular.
- Atualização automática e seleção de período.
- Cards, distribuição, histórico e visão por fonte.
- Nenhum dado pessoal, imagem, biometria ou evento individual é exposto pelo portal.
- CORS opcional por lista explícita de origens.
- Preparado para publicação atrás de Cloudflare Tunnel e Cloudflare Access.

## 0.3.2

- Unifica fontes do Vision com o leitor operacional, evitando entidades `sensor.*` como fonte.
- Associa automaticamente observações HEA ao local do leitor.
- Remove identidade pessoal dos eventos técnicos `vision.analysis_completed` persistidos.
- Exibe a confiança HEA com duas casas decimais.
- Migra e reconcilia fontes técnicas criadas pela versão anterior.
- Mantém compatibilidade com Seiden Bridge 0.6.3 e Seiden Vision 0.4.0.


## 0.3.1
- Corrigida a correlação de leitores nos eventos online/offline.
- Adicionado fallback compatível por `reader_name` e `reader_ip` para eventos de versões anteriores do Bridge.
- Sincronizado o estado operacional nas tabelas `sources_state` e `sources`.
- Mantida compatibilidade com o identificador canônico `reader_id` do Seiden Bridge 0.6.3.


## 0.3.0
- Novo módulo Human Experience Analytics (HEA).
- Novo Observation Engine genérico.
- Novas entidades `Observation` e `ObservationAggregate`.
- Consumo automático de `vision.analysis_completed`.
- Separação entre expressão observada e identidade da pessoa.
- Remoção da emoção do evento técnico persistente do Vision.
- Retenção curta e limpeza automática das observações brutas.
- Agregação configurável por janela de tempo e fonte.
- Quantidade mínima de amostras configurável; abaixo do limite, o dashboard mostra dados insuficientes.
- Confiança mínima configurável.
- Experience Index de -100 a +100.
- Dashboard HEA com índice, distribuição, confiança, amostras e ranking por fonte.
- Novas APIs `/api/v1/hea/*` e `/api/v1/observations`.
- Nova entidade `sensor.seiden_flow_experience_index` no Home Assistant.
- Migração automática e não destrutiva do banco para o schema 3.

## 0.2.1
- Dashboard atualizado automaticamente a cada 5 segundos.
- Temas Escuro, Claro e Automático.

## 0.2.0
- Modelo de domínio e migração automática do banco.

## 0.1.0
- Primeira versão da camada de dados operacional.
