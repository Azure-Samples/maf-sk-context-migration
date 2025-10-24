# Guia de Migracao de Context Engineering

## 1. Contexto e Objetivos

- **Proposito**
  - Estabelecer um plano detalhado para migrar a demonstracao de context engineering para o Microsoft Agent Framework (MAF) preservando resultados e telemetria.
- **Escopo**
  - Diretorio `src/context_engineering`, abrangendo `main.py`, `maf.py`, `sk.py` e `tools.py`.
  - Processos de construcao de contexto e geracao do relatorio `comparison_result.md`.
- **Resultado Esperado**
  - Fluxo unico baseado em MAF com os mesmos artefatos de dados, tempos e logs do pipeline atual do Semantic Kernel (SK).

## 2. Capacidades Existentes

- **Demonstracao com Semantic Kernel**
  - Carrega variaveis de ambiente e configura servicos SK para a implantacao Azure AI.
  - Agrega dados MCP (calendario, cobertura, prioridades) via utilidades do repositorio.
  - Executa planejamento de intencoes, geracao de rascunho e refinamento por meio de prompts SK.
  - Mede tempos com `OperationTracker` e compila o conteudo no relatorio comparativo.
- **Demonstracao com Microsoft Agent Framework**
  - Valida credenciais Azure AI e inicializa o Azure AI Agent Client.
  - Expos ferramentas MCP com `@ai_function`, compartilhando os mesmos utilitarios do repositorio.
  - Cria ChatAgents (facilitador e analista) com instrucoes equivalentes as do SK.
  - Conduz abertura, colaboracao e encerramento em threads persistentes, preservando o historico.
  - Persiste contexto e metricas pelo repositorio e `OperationTracker`.

## 3. Metas de Migracao e Capacidades Mantidas

- **Metas**
  - Eliminar divergencias entre implementacoes, mantendo uma base de ferramentas unificada.
  - Garantir que o Markdown final conserve secoes, titulos e metricas originais.
- **Capacidades Mantidas**
  - Ingestao de dados MCP atraves dos mesmos endpoints.
  - Metricas de duracao e nomes de etapa emitidos pelo `OperationTracker`.
  - Estruturas de contexto (sumario, recomendacoes, proximos passos, riscos).
  - Execucao por linha de comando (`python src/context_engineering/main.py`).

## 4. Plano de Migracao Detalhado

1. **Coleta de Baseline**
   - Executar ambos os fluxos e armazenar JSON/Markdown de referencia.
   - Registrar diferencas observadas em conteudo, ordenacao ou metricas.
2. **Alinhamento de Configuracao**
   - Confirmar variaveis `.env` (`AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `WORKFORCE_MCP_BASE_URL`).
   - Atualizar exemplos de configuracao se encontrar lacunas.
3. **Auditoria de Ferramentas MCP**
   - Revisar `tools.py` para assegurar assinaturas compativeis com SK e MAF.
   - Utilizar tipos genericos (`dict`, `list`) para manter geracao de schema estavel.
4. **Traducao de Prompts**
   - Mapear prompts SK para instrucoes dos agentes MAF, preservando intencao e formato.
   - Centralizar textos em constantes para reduzir divergencias futuras.
5. **Gestao de Threads e Contexto**
   - Garantir reutilizacao da thread durante todo o cenario para manter historico conversacional.
   - Substituir memoria SK por chamadas ao `store_context_tool` e demais utilitarios MCP.
6. **Consistencia de Logs**
   - Proteger fases principais com `OperationTracker` mantendo titulos identicos.
   - Verificar relatorios `comparison_result.md` para confirmar tempos por framework.
7. **Descomissionamento do SK**
   - Apos validacao, marcar `sk.py` como legado ou remove-lo do fluxo de execucao.
   - Atualizar documentacao oficial para recomendar somente o MAF.

## 5. Estrategia de Validacao

- **Testes Funcionais**
  - Rodar `python src/context_engineering/main.py` e comparar o Markdown com o baseline.
  - Garantir que sumarios, recomendacoes e secoes de risco permaneçam identicos.
- **Telemetria**
  - Revisar logs e `OperationTracker` para confirmar duracoes e mensagens equivalentes.
- **Regressao Ampliada**
  - Validar com datasets alternativos (`daily_staff.json`, `daily_updates.json`) para cobrir variacoes.

## 6. Riscos e Mitigacoes

- **Desalinhamento de Ferramentas**
  - *Risco*: Alteracoes nas funcoes MCP causam falhas em um dos frameworks.
  - *Mitigacao*: Centralizar as definicoes em `tools.py` e acrescentar testes rapidos de smoke.
- **Mudanca de Tom nos Prompts**
  - *Risco*: Respostas dos agentes divergem em extensao ou foco.
  - *Mitigacao*: Revisar outputs durante a coleta de baseline e ajustar instrucoes gradualmente.
- **Perda de Telemetria**
  - *Risco*: Remover SK reduz campos de log usados por observabilidade.
  - *Mitigacao*: Conferir `comparison_result.md` antes de desativar codigo SK.
- **Limitacoes de Servico Azure AI**
  - *Risco*: Uso prolongado de threads aumenta consumo.
  - *Mitigacao*: Encerrar threads apos cada execucao e monitorar quotas.

## 7. Checklist Pos-Migracao

- [ ] Caminhos SK desativados em `main.py`.
- [ ] Documentacao atualizada para refletir o fluxo MAF.
- [ ] Markdown validado com multiplos datasets de exemplo.
- [ ] Pipeline de CI executa comparacao automatizada.

## 8. Apendice

- **Arquivos-Chave**
  - `src/context_engineering/main.py`
  - `src/context_engineering/maf.py`
  - `src/context_engineering/tools.py`
  - `src/context_engineering/sk.py` (legado durante a transicao)
- **Dependencias Externas**
  - `agent-framework-core`
  - `semantic-kernel`
  - `azure-identity`
  - Servico MCP de workforce ativo.
