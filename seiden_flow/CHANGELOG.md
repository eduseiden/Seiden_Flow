# Changelog

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
