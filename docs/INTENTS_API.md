# API de Intents - Documentação

Esta documentação descreve como usar os endpoints para gerenciar intents de bots na aplicação WhatsApp.

## 🔒 Autenticação

**TODOS os endpoints de intents requerem autenticação JWT válida**. O `account_id` é extraído automaticamente do token JWT do usuário.

```
Authorization: Bearer SEU_TOKEN_JWT_DO_SUPABASE
```

## Endpoints Disponíveis

### 1. Listar Intents de um Bot
**GET** `/bots/{bot_id}/intents`

Lista todas as intents de um bot específico.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros da URL
- `bot_id`: UUID do bot

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "intents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "bot_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
      "name": "Saudação",
      "intention": "O usuário está cumprimentando ou iniciando uma conversa",
      "active": true,
      "prompt": "Responda de forma amigável e educada à saudação do usuário",
      "function_id": null
    }
  ],
  "total": 1,
  "bot_id": "3d0477ad-537b-4364-94bd-cd46acec2136"
}
```

### 2. Criar Intent
**POST** `/bots/{bot_id}/intents`

Cria uma nova intent para um bot.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Parâmetros da URL
- `bot_id`: UUID do bot

#### Corpo da Requisição
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Saudação",
  "intention": "O usuário está cumprimentando ou iniciando uma conversa",
  "active": true,
  "prompt": "Responda de forma amigável e educada à saudação do usuário",
  "function_id": null
}
```

#### Campos Obrigatórios
- `id`: UUID v4 válido (gerado no front-end)

#### Campos Opcionais
- `name`: Nome da intent (máximo 50 caracteres)
- `intention`: Descrição da intenção/propósito da intent (texto)
- `active`: Indica se a intent está ativa (boolean, padrão: true)
- `prompt`: Prompt específico para esta intent (texto)
- `function_id`: ID da função associada à intent (máximo 150 caracteres)

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Intent criada com sucesso",
  "status": "success",
  "intent": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "bot_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "name": "Saudação",
    "intention": "O usuário está cumprimentando ou iniciando uma conversa",
    "active": true,
    "prompt": "Responda de forma amigável e educada à saudação do usuário",
    "function_id": null
  }
}
```

### 3. Buscar Intent por ID
**GET** `/bots/{bot_id}/intents/{intent_id}`

Busca uma intent específica pelo seu ID.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros da URL
- `bot_id`: UUID do bot
- `intent_id`: UUID da intent a ser buscada

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "intent": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "bot_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "name": "Saudação",
    "intention": "O usuário está cumprimentando ou iniciando uma conversa",
    "active": true,
    "prompt": "Responda de forma amigável e educada à saudação do usuário",
    "function_id": null
  }
}
```

### 4. Atualizar Intent
**PUT** `/bots/{bot_id}/intents/{intent_id}`

Atualiza uma intent existente. Apenas os campos fornecidos são atualizados.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Parâmetros da URL
- `bot_id`: UUID do bot
- `intent_id`: UUID da intent a ser atualizada

#### Corpo da Requisição (Todos os campos são opcionais)
```json
{
  "name": "Saudação Melhorada",
  "intention": "O usuário está cumprimentando, iniciando uma conversa ou sendo cordial",
  "active": true,
  "prompt": "Responda de forma muito amigável e educada à saudação do usuário, demonstrando empatia",
  "function_id": "func_123"
}
```

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Intent atualizada com sucesso",
  "status": "success",
  "intent": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "bot_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "name": "Saudação Melhorada",
    "intention": "O usuário está cumprimentando, iniciando uma conversa ou sendo cordial",
    "active": true,
    "prompt": "Responda de forma muito amigável e educada à saudação do usuário, demonstrando empatia",
    "function_id": "func_123"
  },
  "updated_fields": ["name", "intention", "prompt", "function_id"]
}
```

### 5. Deletar Intent
**DELETE** `/bots/{bot_id}/intents/{intent_id}`

**⚠️ ATENÇÃO: Esta operação deleta permanentemente a intent do banco de dados e não pode ser desfeita.**

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros da URL
- `bot_id`: UUID do bot
- `intent_id`: UUID da intent a ser deletada

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Intent deletada permanentemente com sucesso",
  "status": "success",
  "intent_id": "550e8400-e29b-41d4-a716-446655440000",
  "bot_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
  "action": "deletada permanentemente"
}
```

## Exemplos de Uso

### Usando cURL

#### Listar intents de um bot:
```bash
curl -X GET https://atendimento.pluggerbi.com/bots/3d0477ad-537b-4364-94bd-cd46acec2136/intents \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

#### Criar intent:
```bash
curl -X POST https://atendimento.pluggerbi.com/bots/3d0477ad-537b-4364-94bd-cd46acec2136/intents \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Solicitação de Ajuda",
    "intention": "O usuário está pedindo ajuda ou suporte",
    "active": true,
    "prompt": "Ofereça ajuda de forma proativa e pergunte como pode assistir o usuário"
  }'
```

#### Atualizar intent:
```bash
curl -X PUT https://atendimento.pluggerbi.com/bots/3d0477ad-537b-4364-94bd-cd46acec2136/intents/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pedido de Suporte Avançado",
    "prompt": "Ofereça suporte técnico detalhado e pergunte especificamente sobre o problema"
  }'
```

#### Deletar intent permanentemente:
```bash
curl -X DELETE https://atendimento.pluggerbi.com/bots/3d0477ad-537b-4364-94bd-cd46acec2136/intents/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Usando JavaScript (Frontend)

#### Listar intents:
```javascript
async function getBotIntents(jwtToken, botId) {
  try {
    const response = await fetch(`/bots/${botId}/intents`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Intents:', result.intents);
      return result.intents;
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

#### Criar intent:
```javascript
async function createIntent(jwtToken, botId, intentData) {
  try {
    const response = await fetch(`/bots/${botId}/intents`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(intentData)
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Intent criada:', result.intent);
      return result.intent;
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
const intentData = {
  id: generateUUID(),
  name: 'Despedida',
  intention: 'O usuário está se despedindo ou encerrando a conversa',
  active: true,
  prompt: 'Responda de forma cordial à despedida e deseje um bom dia'
};

createIntent(jwtToken, botId, intentData)
  .then(intent => console.log('Sucesso:', intent))
  .catch(error => console.error('Falha:', error));
```

## Códigos de Status HTTP

- **200 OK**: Operação realizada com sucesso
- **201 Created**: Intent criada com sucesso
- **400 Bad Request**: Dados inválidos ou ausentes / Token JWT sem account_id
- **401 Unauthorized**: Token JWT ausente, inválido ou expirado
- **403 Forbidden**: Acesso negado - bot não pertence à sua conta
- **404 Not Found**: Bot ou intent não encontrado
- **409 Conflict**: Intent com o mesmo ID já existe para este bot
- **500 Internal Server Error**: Erro interno do servidor
- **503 Service Unavailable**: Banco de dados não está habilitado

## Estrutura da Tabela Intents

```sql
CREATE TABLE `intents` (
  `id` varchar(36) NOT NULL,
  `bot_id` varchar(36) NOT NULL,
  `name` varchar(50) DEFAULT NULL,
  `intention` text,
  `active` tinyint(1) DEFAULT '1',
  `prompt` text,
  `function_id` varchar(150) DEFAULT NULL,
  PRIMARY KEY (`id`,`bot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

## Exemplos de Intents

### Intent de Saudação
```json
{
  "id": "uuid-saudacao",
  "bot_id": "uuid-bot",
  "name": "Saudação",
  "intention": "O usuário está cumprimentando, dizendo olá, oi, bom dia, boa tarde ou boa noite",
  "active": true,
  "prompt": "Responda de forma amigável e educada à saudação. Pergunte como pode ajudar.",
  "function_id": null
}
```

### Intent de Solicitação de Ajuda
```json
{
  "id": "uuid-ajuda",
  "bot_id": "uuid-bot",
  "name": "Pedido de Ajuda",
  "intention": "O usuário está pedindo ajuda, suporte, assistência ou tem uma dúvida",
  "active": true,
  "prompt": "Demonstre disponibilidade para ajudar e peça detalhes sobre o que o usuário precisa.",
  "function_id": "support_function"
}
```

### Intent de Informações de Produto
```json
{
  "id": "uuid-produto",
  "bot_id": "uuid-bot",
  "name": "Informações de Produto",
  "intention": "O usuário quer saber sobre produtos, preços, características ou especificações",
  "active": true,
  "prompt": "Forneça informações detalhadas sobre produtos e pergunte se precisa de algo específico.",
  "function_id": "product_info_function"
}
```

### Intent de Despedida
```json
{
  "id": "uuid-despedida",
  "bot_id": "uuid-bot",
  "name": "Despedida",
  "intention": "O usuário está se despedindo, encerrando a conversa ou agradecendo",
  "active": true,
  "prompt": "Responda cordialmente à despedida e deixe a porta aberta para futuras conversas.",
  "function_id": null
}
```

## Segurança e Permissões

1. **Isolamento por Conta**: Usuários só podem acessar intents de bots da própria conta
2. **Validação JWT**: Todos os endpoints requerem token válido
3. **Validação de UUID**: IDs são validados como UUID v4
4. **Validação de Propriedade**: Verifica se o bot pertence à conta antes de manipular intents
5. **Sanitização**: Dados são sanitizados antes de armazenar
6. **Logs de Auditoria**: Todas as operações são logadas
7. **Validação de Tamanhos**: Campos têm limites de caracteres

## Notas Importantes

1. **Bot ID**: Obrigatório em todos os endpoints - define a qual bot a intent pertence
2. **Intent ID**: UUID gerado no frontend para identificação única
3. **Campos Opcionais**: Todos os campos exceto ID são opcionais na criação
4. **Campo Active**: Controla se a intent está ativa (padrão: true)
5. **Function ID**: Pode referenciar funções específicas do bot
6. **Delete Permanente**: DELETE remove a intent completamente do banco de dados
7. **Chave Composta**: A tabela usa chave primária composta (id, bot_id)
8. **Ordenação**: Intents são retornadas ordenadas por nome (ASC)

## Integração com Bots

As intents criadas podem ser utilizadas pelo sistema de IA para:

- **Classificação de Mensagens**: Identificar a intenção do usuário
- **Roteamento de Conversas**: Direcionar para fluxos específicos
- **Personalização de Respostas**: Usar prompts específicos para cada intent
- **Execução de Funções**: Chamar functions associadas às intents
- **Análise de Comportamento**: Coletar dados sobre as intenções mais comuns

Cada intent pode ter um prompt específico que será usado quando essa intenção for detectada, permitindo respostas mais contextualizadas e personalizadas.
