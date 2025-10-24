# Comparativo de Engenharia de Contexto: Semantic Kernel vs. Microsoft Agent Framework

Este repositório demonstra como realizar engenharia de contexto em conversas utilizando o **Semantic Kernel** (SK) e o **Microsoft Agent Framework** (MAF). As duas implementações estão organizadas em `src/context_engineering/` e compartilham utilitários e logs para facilitar a comparação.

Os exemplos mostram:

- Um fluxo baseado em máquina de estados para cada framework, destacando a evolução do contexto.
- Um repositório de contexto persistido em disco, permitindo inspecionar cada alteração.
- Execução paralela baseada em threads com métricas de tempo para avaliar desempenho relativo.

## Estrutura do Repositório

```text
src/
  context_engineering/
    main.py        # Orquestração em threads e geração de métricas
    sk.py          # Máquina de estados do Semantic Kernel e execução de prompts
    maf.py         # Máquina de estados do Microsoft Agent Framework e interações
    tools.py       # Utilidades compartilhadas, armazenamento de contexto e ferramentas decoradas
```

O script `main.py` executa os dois fluxos em paralelo, consolida os resultados e imprime um objeto JSON com métricas de tempo. Cada implementação depende de `tools.py` para logging, validação de ambiente e persistência do contexto.

## Semantic Kernel vs. Microsoft Agent Framework

| Aspecto                      | Semantic Kernel (SK)                                                                 | Microsoft Agent Framework (MAF)                                                        |
|-----------------------------|--------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Manipulação de contexto     | Atualizações imperativas via helpers decorados (`SemanticKernelTools`).              | Ferramentas decoradas (`AgentFrameworkTools`) expõem as mesmas primitivas de persistência. |
| Controle de threads         | Utiliza threads do SK e argumentos de prompt com renderização explícita do contexto.| Usa threads do MAF via `ChatAgent.get_new_thread()` e envia mensagens formatadas.       |
| Padrão de estados           | `SKAddInstructionsState`, `SKPlanWorkshopState`, etc.                               | `AFAddBriefingState`, `AFFirstInteractionState`, etc.                                  |
| Estratégia de limpeza       | Remove chaves transitórias após finalizar o plano.                                  | Substitui o contexto para simular agendas em evolução.                                 |
| Captura de resultados       | Armazena a última resposta do SK para auditoria.                                    | Agrega todas as respostas do facilitador para inspeção.                                |

O `ContextRepository` comum faz com que ambos os fluxos persistam suas modificações em `context_store.json`. Inspecione este arquivo para acompanhar a evolução dos valores.

## Guia de Migração: do Semantic Kernel para o Agent Framework

1. **Mapeie as operações de contexto**  
   - No SK, as atualizações acontecem via plugins do kernel ou manipulação direta de dicionários.  
   - No MAF, replique essas operações como ferramentas decoradas com `@ai_function` para que os agentes possam chamá-las.

2. **Refatore o fluxo em estados**  
   - Transfira cada etapa lógica (instruções, agenda, limpeza) para classes específicas que herdam de uma base comum.  
   - Reutilize nomes equivalentes entre SK e MAF para facilitar testes paralelos.

3. **Gerencie threads de conversa**  
   - Substitua objetos de thread do SK por instâncias `ChatAgent.get_new_thread()`.  
   - Garanta que as mensagens levem o contexto formatado por `_compose_dynamic_message`, replicando os dados incluídos nos prompts do SK.

4. **Exponha ferramentas**  
   - Encapsule os helpers do repositório (armazenar, remover, substituir) com os decoradores adequados.  
   - Registre as ferramentas ao criar o agente do MAF para que o framework possa acioná-las durante a execução.

5. **Valide e monitore**  
   - Continue usando o `OperationTracker` para verificar ordem e duração das operações.  
   - Após migrar, execute `python -m context_engineering.main` e compare os snapshots de contexto e as respostas.

## Execução dos Exemplos

1. Instale as dependências com o ambiente virtual ativado:

   ```bash
   uv add semantic-kernel agent-framework azure-ai-sdk python-dotenv
   ```

2. Configure as variáveis de ambiente necessárias para ambos os frameworks:

   ```powershell
   $env:AZURE_OPENAI_ENDPOINT = "https://<seu-endpoint>.openai.azure.com"
   $env:AZURE_OPENAI_CHAT_DEPLOYMENT_NAME = "<nome-do-deployment>"
   $env:AZURE_AI_PROJECT_ENDPOINT = "https://<seu-projeto>.agents.azure.com"
   $env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "<deployment-do-agente>"
   ```

3. Execute o comparativo:

   ```bash
   python -m context_engineering.main
   ```

4. Inspecione `context_store.json` para revisar o histórico e acompanhe os logs para ver a distribuição de tempo.

## Recursos Adicionais

- [Documentação do Semantic Kernel](https://learn.microsoft.com/semantic-kernel/)
- [Amostras do Microsoft Agent Framework](https://github.com/microsoft/Agent-Framework-Samples)

Adapte as máquinas de estado conforme necessário para refletir a realidade do seu projeto. A infraestrutura de comparação presente neste repositório deve ajudar a validar o comportamento antes e depois da migração.
