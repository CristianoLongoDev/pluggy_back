# API de Bots - Documentação

Esta documentação descreve como usar os endpoints para gerenciar bots na aplicação WhatsApp.

## 🔒 Autenticação

**TODOS os endpoints de bots requerem autenticação JWT válida**. O `account_id` é extraído automaticamente do token JWT do usuário.

```
Authorization: Bearer SEU_TOKEN_JWT_DO_SUPABASE
```

## Endpoints Disponíveis

### 1. Listar Bots
**GET** `/bots`

Lista todos os bots da conta do usuário autenticado.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bots": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
      "name": "Bot de Suporte",
      "system_prompt": "Você é um assistente de suporte técnico especializado em resolver problemas de clientes de forma rápida e eficiente...",
      "integration_id": "789e0123-e89b-12d3-a456-426614174000",
      "agent_name": "Assistente Virtual",
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1,
  "security_info": {
    "filtered_by_account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "user_id": "uuid-do-usuario",
    "user_email": "usuario@exemplo.com",
    "query_timestamp": "2025-01-15T16:45:00.000000"
  }
}
```

### 2. Criar Bot
**POST** `/bots`

Cria um novo bot.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Corpo da Requisição
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Bot de Suporte",
  "system_prompt": "Você é um assistente de suporte técnico especializado em resolver problemas de clientes de forma rápida e eficiente. Suas principais responsabilidades incluem: 1) Diagnosticar problemas técnicos, 2) Fornecer soluções claras e práticas, 3) Escalar para suporte humano quando necessário.",
  "integration_id": "789e0123-e89b-12d3-a456-426614174000",
  "agent_name": "Assistente Virtual"
}
```

#### Campos Obrigatórios
- `id`: UUID v4 válido (gerado no front-end)
- `name`: Nome do bot (máximo 100 caracteres)
- `system_prompt`: Prompt do sistema que define o comportamento do bot (máximo 10000 caracteres)

#### Campos Opcionais
- `integration_id`: UUID da integração associada ao bot
- `agent_name`: Nome do agente que aparecerá nas mensagens (máximo 100 caracteres)

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Bot criado com sucesso",
  "status": "success",
  "bot": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "name": "Bot de Suporte",
    "system_prompt": "Você é um assistente de suporte técnico...",
    "integration_id": "789e0123-e89b-12d3-a456-426614174000",
    "agent_name": "Assistente Virtual",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

### 3. Buscar Bot por ID
**GET** `/bots/{bot_id}`

Busca um bot específico pelo seu ID.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros da URL
- `bot_id`: UUID do bot a ser buscado

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bot": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "name": "Bot de Suporte",
    "system_prompt": "Você é um assistente de suporte técnico...",
    "integration_id": "789e0123-e89b-12d3-a456-426614174000",
    "agent_name": "Assistente Virtual",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

### 4. Atualizar Bot
**PUT** `/bots/{bot_id}`

Atualiza um bot existente. Apenas os campos fornecidos são atualizados.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Corpo da Requisição (Todos os campos são opcionais)
```json
{
  "name": "Bot de Suporte Avançado",
  "system_prompt": "Você é um assistente avançado de suporte técnico com especialização em IA e automação. Suas capacidades incluem: 1) Análise avançada de problemas, 2) Sugestões de otimização, 3) Integração com sistemas externos.",
  "integration_id": "789e0123-e89b-12d3-a456-426614174000",
  "agent_name": "Assistente Virtual"
}
```

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Bot atualizado com sucesso",
  "status": "success",
  "bot": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "name": "Bot de Suporte Avançado",
    "system_prompt": "Você é um assistente avançado de suporte técnico...",
    "integration_id": "789e0123-e89b-12d3-a456-426614174000",
    "agent_name": "Assistente Virtual",
    "created_at": "2024-01-15T10:30:00"
  },
  "updated_fields": ["name", "system_prompt", "integration_id"]
}
```

### 5. Deletar Bot
**DELETE** `/bots/{bot_id}`

**⚠️ ATENÇÃO: Esta operação deleta permanentemente o bot do banco de dados e não pode ser desfeita.**

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Bot deletado permanentemente com sucesso",
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "action": "deletado permanentemente"
}
```

## Exemplos de Uso

### Usando cURL

#### Listar bots:
```bash
curl -X GET https://atendimento.pluggerbi.com/bots \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

#### Criar bot:
```bash
curl -X POST https://atendimento.pluggerbi.com/bots \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Bot de Vendas",
    "system_prompt": "Você é um assistente de vendas especializado em conversão de leads. Sempre seja amigável, profissional e focado em entender as necessidades do cliente.",
    "integration_id": "789e0123-e89b-12d3-a456-426614174000",
    "agent_name": "Consultor de Vendas"
  }'
```

#### Atualizar bot:
```bash
curl -X PUT https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bot de Vendas Premium",
    "system_prompt": "Você é um assistente premium de vendas com foco em produtos de alto valor...",
    "agent_name": "Especialista Premium"
  }'
```

#### Deletar bot permanentemente:
```bash
curl -X DELETE https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Usando JavaScript (Frontend)

#### Listar bots:
```javascript
async function getBots(jwtToken) {
  try {
    const response = await fetch('/bots', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Bots:', result.bots);
      return result.bots;
    } else {
      console.error('Erro:', result.error);
      return null;
    }
  } catch (error) {
    console.error('Erro na requisição:', error);
    return null;
  }
}
```

#### Criar bot:
```javascript
async function createBot(jwtToken, botData) {
  try {
    const response = await fetch('/bots', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(botData)
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Bot criado:', result.bot);
      return result.bot;
    } else {
      console.error('Erro:', result.error);
      throw new Error(result.error);
    }
  } catch (error) {
    console.error('Erro na requisição:', error);
    throw error;
  }
}

// Exemplo de uso
const botData = {
  id: generateUUID(),
  name: 'Bot de FAQ',
  system_prompt: 'Você é um bot especializado em responder perguntas frequentes sobre nossos produtos e serviços. Seja claro, objetivo e sempre direcione para mais informações quando necessário.',
  integration_id: '789e0123-e89b-12d3-a456-426614174000',
  agent_name: 'Assistente FAQ'
};

createBot(jwtToken, botData)
  .then(bot => console.log('Sucesso:', bot))
  .catch(error => console.error('Falha:', error));
```

## Códigos de Status HTTP

- **200 OK**: Operação realizada com sucesso
- **201 Created**: Bot criado com sucesso
- **400 Bad Request**: Dados inválidos ou ausentes / Token JWT sem account_id
- **401 Unauthorized**: Token JWT ausente, inválido ou expirado
- **403 Forbidden**: Acesso negado - bot não pertence à sua conta
- **404 Not Found**: Bot não encontrado
- **409 Conflict**: Bot com o mesmo ID já existe
- **500 Internal Server Error**: Erro interno do servidor
- **503 Service Unavailable**: Banco de dados não está habilitado

## Integration ID

O campo `integration_id` permite associar o bot a uma integração específica (como Movidesk, ChatGPT, etc.), permitindo funcionalidades especializadas baseadas no tipo de integração configurada.

## Exemplos de System Prompts

### Bot de Suporte
```text
Você é um assistente de suporte técnico especializado em resolver problemas de clientes de forma rápida e eficiente. Suas principais responsabilidades incluem:

1. Diagnosticar problemas técnicos com base nas informações fornecidas
2. Fornecer soluções claras e práticas passo a passo
3. Escalar para suporte humano quando o problema for complexo demais
4. Manter um tom profissional e empático em todas as interações
5. Sempre perguntar por informações adicionais quando necessário
```

### Bot de Vendas
```text
Você é um assistente de vendas especializado em conversão de leads e fechamento de negócios. Suas diretrizes são:

1. Sempre seja amigável, profissional e consultivo
2. Faça perguntas para entender as necessidades do cliente
3. Apresente soluções que realmente atendam às necessidades identificadas
4. Use técnicas de vendas consultivas, não agressivas
5. Forneça informações claras sobre preços, prazos e condições
6. Saiba quando transferir para um vendedor humano
```

### Bot de FAQ
```text
Você é um bot especializado em responder perguntas frequentes sobre produtos e serviços. Suas características:

1. Seja claro, objetivo e direto nas respostas
2. Use informações precisas e atualizadas
3. Quando não souber a resposta, direcione para canais apropriados
4. Forneça links ou referências quando relevante
5. Mantenha as respostas organizadas e fáceis de entender
6. Sempre ofereça ajuda adicional ao final
```

### Bot com Integração Movidesk
```text
Você é um assistente especializado em integração com o sistema Movidesk para suporte técnico. Suas responsabilidades incluem:

1. Auxiliar na criação e gestão de tickets no Movidesk
2. Fornecer informações sobre status de solicitações
3. Integrar dados entre WhatsApp e sistema Movidesk
4. Facilitar a comunicação entre clientes e equipe de suporte
5. Automatizar processos de abertura e acompanhamento de chamados
6. Manter sincronização de informações entre os sistemas
```

## Segurança e Permissões

1. **Isolamento por Conta**: Usuários só podem acessar bots da própria conta
2. **Validação JWT**: Todos os endpoints requerem token válido
3. **Validação de UUID**: IDs são validados como UUID v4
4. **Sanitização**: Dados são sanitizados antes de armazenar
5. **Logs de Auditoria**: Todas as operações são logadas
6. **Validação de Tamanhos**: Campos têm limites de caracteres
7. **Tipos Controlados**: Apenas tipos pré-definidos são aceitos

## Notas Importantes

1. **Account ID**: Extraído automaticamente do token JWT (`user_metadata.account_id`)
2. **Delete Permanente**: DELETE remove o bot completamente do banco de dados
3. **System Prompt**: Campo text que suporta prompts longos e detalhados
4. **Relacionamentos**: Bots podem ser referenciados por channels via `bot_id`
5. **Segurança**: Operações de DELETE são irreversíveis
6. **Validações**: Tamanhos de campos são validados tanto no frontend quanto backend
7. **Tipos**: Lista de tipos válidos pode ser expandida conforme necessário

## Integração com Channels

Os bots criados podem ser associados a channels através do campo `bot_id`:

```json
{
  "id": "channel-uuid",
  "type": "whatsapp",
  "name": "WhatsApp Principal",
  "bot_id": "bot-uuid",  // ← Referência ao bot
  "config": {...}
}
```

Isso permite que cada canal tenha um comportamento específico baseado no bot associado. 