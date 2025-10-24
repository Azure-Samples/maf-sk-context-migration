# Guia de Migracao da Conversa de Agentes

## 1. Contexto e Visao

- **Objetivo**
  - Definir um roteiro detalhado para consolidar o executor de cenarios no Microsoft Agent Framework (MAF) sem perder funcionalidades de analise de forca de trabalho.
- **Escopo**
  - Fluxos em `src/agent_conversation`, incluindo `main.py`, `scenario_strategies.py`, `maf.py` e `tools.py`.
  - Cenarios `coverage_assessment` e `future_staffing`.
- **Resultado Almejado**
  - Plataforma unificada baseada em MAF com logs, metricas e resultados equivalentes ao fluxo atual do Semantic Kernel (SK).

## 2. Capacidades Atuais

- **Executor com Semantic Kernel**
  - Carrega variaveis do `.env` e valida identificadores da implantacao Azure AI.
  - Cria agentes temporarios (pesquisador e planejador) a cada execucao.
  - Usa `ConversationToolsPlugin` para consultar endpoints MCP (`evaluate_workforce`, `get_staff_schedule`, etc.).
  - Persiste contexto via plugin e registra operacoes com `OperationTracker`.
  - Remove agentes remotos ao termino para evitar acumulo de recursos.
- **Executor com Microsoft Agent Framework**
  - Valida credenciais Azure AI e instancia `ChatAgent` persistentes (facilitador e especialista).
  - Compartilha ferramentas MCP via funcoes `@ai_function` (`store_context_tool`, `evaluate_workforce_tool`, etc.).
  - Conduz sequencia completa (abertura, resposta, follow-up, fechamento) reutilizando threads.
  - Registra metricas de tempo e observabilidade detalhada atraves do middleware do MAF.

## 3. Metas de Migracao e Capacidades Preservadas

- **Metas**
  - Substituir o executor SK por MAF mantendo comportamento de cenario, dados e logs.
  - Reduzir codigo duplicado e padronizar instrumentos de telemetria.
- **Capacidades Preservadas**
  - Leitura de dados MCP (`/workforce/schedule`, `/workforce/coverage`, etc.).
  - Estrutura de contexto (resumo do cenario, respostas de agentes, notas de follow-up).
  - Metricas consolidadas pelo `OperationTracker`.
  - Registro de eventos com etiquetas de framework e fase.

## 4. Plano Detalhado de Migracao

1. **Inventario e Baseline**
   - Mapear dependencias entre `sk.py`, `tools.py` e cenarios.
   - Capturar `comparison_result.md` como referencia do estado atual.
2. **Alinhamento de Configuracao**
   - Garantir variaveis `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME` e `WORKFORCE_MCP_BASE_URL` definidas.
   - Documentar variaveis adicionais em `README.md` ou `.env.sample`.
3. **Validacao das Ferramentas MCP**
   - Conferir que utilitarios declarados com `@ai_function` aceitam os mesmos parametros usados pelo SK.
   - Ajustar tipagens para evitar problemas de geracao de schema (ja atualizado para `dict`, `list`).
4. **Mapeamento de Prompts**
   - Converter prompts do pesquisador/planejador em instrucoes equivalentes para facilitador/especialista.
   - Garantir que todas as mensagens criticas tenham contrapartida no fluxo MAF.
5. **Gestao de Threads e Contexto**
   - Substituir armazenamento via plugin por chamadas explicitas ao `store_context_tool` dentro do MAF.
   - Reutilizar a mesma thread durante toda a conversa para preservar historico.
6. **Padronizacao de Logs**
   - Confirmar que cada etapa do MAF esta protegida por `OperationTracker` e logs estruturados.
   - Manter logs por cenario introduzidos em `scenario_strategies.py` (status e elapsed_ms).
7. **Desativacao do Fluxo SK**
   - Apos validacao, marcar `sk.py` como legado ou remove-lo do caminho de execucao.
   - Atualizar documentacao para apontar o fluxo oficial (MAF).

## 5. Estrategia de Testes

- **Execucoes Automatizadas**
  - Rodar `python src/agent_conversation/main.py` com selecoes `coverage` e `forward`.
  - Comparar JSON de saida com baseline armazenado durante o inventario.
- **Consistencia de Dados**
  - Conferir que os relatorios de cobertura e escalas apresentem as mesmas recomendacoes.
- **Observabilidade**
  - Garantir que `comparison_result.md` contenha os novos logs e metricas esperadas.

## 6. Riscos e Mitigacoes

- **Divergencia de Ferramentas**
  - *Risco*: Assinaturas de funcoes MCP mudam e quebram automacoes.
  - *Mitigacao*: Centralizar todas as definicoes em `tools.py` e validar com testes de fumaca.
- **Alteracao de Comportamento dos Prompts**
  - *Risco*: Mensagens finais diferem do esperado.
  - *Mitigacao*: Manter prompts originais durante a migracao e documentar quaisquer ajustes necessarios.
- **Limites de Servico Azure AI**
  - *Risco*: Uso intensivo de ChatAgents atinge limites de execucao.
  - *Mitigacao*: Encerrar threads apos cada conversa e monitorar dashboards de consumo.
- **Perda de Telemetria**
  - *Risco*: Faltam metricas para depuracao.
  - *Mitigacao*: Validar presenca de spans `OperationTracker` e logs por etapa antes de deprecar SK.

## 7. Checklist Pos-Migracao

- [ ] SK removido ou sinalizado como legado.
- [ ] `comparison_result.md` exibe exclusivamente execucoes MAF.
- [ ] Documentacao interna atualizada com novos comandos de execucao.
- [ ] Rotina de CI validando `main.py` com ambiente de teste.

## 8. Apendice

- **Arquivos-Chave**
  - `src/agent_conversation/main.py`
  - `src/agent_conversation/maf.py`
  - `src/agent_conversation/tools.py`
  - `src/agent_conversation/scenario_strategies.py`
- **Dependencias Externas**
  - `agent-framework-core`
  - `semantic-kernel`
  - `azure-identity`
  - Servico MCP de workforce (FastAPI) ativo.
