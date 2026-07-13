# Hybrid Service Desk Agent

Agente de atendimento executado no Amazon Bedrock AgentCore Runtime com LangGraph, memória de curto prazo, confirmação humana e criação de chamado.

> **Status:** funcional com AWS. O frontend local chama uma API Gateway/Lambda que invoca o AgentCore Runtime. O grafo LangGraph usa Nova 2 Lite para extrair os dados de cada turno, AgentCore Memory para checkpoints por sessão e DynamoDB para o chamado confirmado.

```bash
make install
make deploy
make seed
make dev
```

A interface local abre em `http://localhost:3100` e encaminha as mensagens para a API AWS. Informe um problema, confira os campos identificados e confirme: um chamado `INC-...` é gravado de verdade no DynamoDB pelo runtime. Antes do deploy, valide as credenciais com `make doctor`. Para remover os recursos temporários após a gravação, execute `make destroy`.

```mermaid
stateDiagram-v2
  [*] --> Entender
  Entender --> Coletar
  Coletar --> Validar
  Validar --> Classificar: completo
  Classificar --> Confirmar
  Confirmar --> Criar: aprovado
  Confirmar --> Coletar: corrigir
  Criar --> Concluído
```

Os arquivos locais gerados pelo deploy (`.env.aws` e `apps/web/config.local.js`) não são versionados.
