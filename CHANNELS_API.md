# API de Canais de Atendimento - Documentação

Esta documentação descreve como usar os endpoints para gerenciar canais de atendimento na aplicação WhatsApp.

## 🔒 Autenticação

**TODOS os endpoints de channels requerem autenticação JWT válida**. O `account_id` é extraído automaticamente do token JWT do usuário.

```
Authorization: Bearer SEU_TOKEN_JWT_DO_SUPABASE
```

## 🔐 Segurança de Dados

**Os campos sensíveis (`client_id`, `client_secret`, `access_token`) NÃO são retornados nas consultas GET por motivos de segurança.** Estes campos só podem ser definidos durante a criação (POST) ou atualização (PUT) do canal.

## Endpoints Disponíveis

### 1. Listar Canais
**GET** `/channels`

Lista todos os canais da conta do usuário autenticado.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros de Query (Opcionais)
- `active_only`: `true` para listar apenas canais ativos (padrão: `false`)

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "channels": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
      "bot_id": "123e4567-e89b-12d3-a456-426614174000",
      "type": "whatsapp",
      "name": "WhatsApp Principal",
      "phone_number": "+5511999999999",
      "active": true,
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1,
  "filters": {
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "active_only": false
  }
}
```

### 2. Criar Canal
**POST** `/channels`

Cria um novo canal de atendimento.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Corpo da Requisição
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "whatsapp",
  "name": "WhatsApp Principal",
  "bot_id": "123e4567-e89b-12d3-a456-426614174000",
  "phone_number": "+5511999999999",
  "client_id": "seu_client_id_aqui",
  "client_secret": "seu_client_secret_aqui",
  "access_token": "seu_access_token_aqui",
  "active": true
}
```

#### Campos Obrigatórios
- `id`: UUID v4 válido (gerado no front-end)
- `type`: Tipo do canal (`whatsapp`, `instagram`, `chat_widget`)

#### Campos Opcionais
- `name`: Nome amigável do canal
- `bot_id`: UUID do bot associado ao canal
- `phone_number`: Número de telefone do canal
- `client_id`: ID do cliente para integração
- `client_secret`: Secret do cliente para integração
- `access_token`: Token de acesso para a API
- `active`: Status ativo/inativo (padrão: `true`)

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Canal criado com sucesso",
  "status": "success",
  "channel": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "bot_id": "123e4567-e89b-12d3-a456-426614174000",
    "type": "whatsapp",
    "name": "WhatsApp Principal",
    "phone_number": "+5511999999999",
    "active": true,
    "created_at": "2024-01-15T10:30:00"
  }
}
```

### 3. Buscar Canal por ID
**GET** `/channels/{channel_id}`

Busca um canal específico pelo seu ID.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros da URL
- `channel_id`: UUID do canal a ser buscado

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "channel": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "bot_id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "WhatsApp Principal",
    "integration_id": "789e0123-e89b-12d3-a456-426614174000",
    "active": true,
    "created_at": "2024-01-15T10:30:00"
  }
}
```

### 4. Atualizar Canal
**PUT** `/channels/{channel_id}`

Atualiza um canal existente. Apenas os campos fornecidos são atualizados.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Corpo da Requisição (Todos os campos são opcionais)
```json
{
  "name": "WhatsApp Atualizado",
  "bot_id": "456e7890-e89b-12d3-a456-426614174000",
  "type": "whatsapp",
  "phone_number": "+5511888888888",
  "client_id": "novo_client_id",
  "client_secret": "novo_client_secret",
  "access_token": "novo_access_token",
  "active": false
}
```

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Canal atualizado com sucesso",
  "status": "success",
  "channel": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "bot_id": "456e7890-e89b-12d3-a456-426614174000",
    "type": "whatsapp",
    "name": "WhatsApp Atualizado",
    "phone_number": "+5511888888888",
    "active": false,
    "created_at": "2024-01-15T10:30:00"
  },
  "updated_fields": ["name", "bot_id", "type", "phone_number", "active"]
}
```

### 5. Deletar Canal
**DELETE** `/channels/{channel_id}`

**⚠️ ATENÇÃO: Esta operação deleta permanentemente o canal do banco de dados e não pode ser desfeita.**

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Canal deletado permanentemente com sucesso",
  "status": "success",
  "channel_id": "550e8400-e29b-41d4-a716-446655440000",
  "action": "deletado permanentemente"
}
```

## Exemplos de Uso

### Usando cURL

#### Listar canais:
```bash
curl -X GET https://atendimento.pluggerbi.com/channels \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

#### Criar canal WhatsApp:
```bash
curl -X POST https://atendimento.pluggerbi.com/channels \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "whatsapp",
    "name": "WhatsApp Principal",
    "whatsapp_phone_number": "+5511999999999"
  }'
```

#### Atualizar canal:
```bash
curl -X PUT https://atendimento.pluggerbi.com/channels/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "WhatsApp Atualizado",
    "active": false
  }'
```

#### Deletar canal permanentemente:
```bash
curl -X DELETE https://atendimento.pluggerbi.com/channels/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Usando JavaScript (Frontend)

#### Listar canais:
```javascript
async function getChannels(jwtToken, activeOnly = false) {
  try {
    const url = `/channels${activeOnly ? '?active_only=true' : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Canais:', result.channels);
      return result.channels;
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

#### Criar canal:
```javascript
async function createChannel(jwtToken, channelData) {
  try {
    const response = await fetch('/channels', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(channelData)
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Canal criado:', result.channel);
      return result.channel;
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
const channelData = {
  id: generateUUID(),
  type: 'whatsapp',
  name: 'WhatsApp Principal',
  config: {
    phone_number: '+5511999999999',
    webhook_url: 'https://example.com/webhook'
  }
};

createChannel(jwtToken, channelData)
  .then(channel => console.log('Sucesso:', channel))
  .catch(error => console.error('Falha:', error));
```

## Códigos de Status HTTP

- **200 OK**: Operação realizada com sucesso
- **201 Created**: Canal criado com sucesso
- **400 Bad Request**: Dados inválidos ou ausentes / Token JWT sem account_id
- **401 Unauthorized**: Token JWT ausente, inválido ou expirado
- **403 Forbidden**: Acesso negado - canal não pertence à sua conta
- **404 Not Found**: Canal não encontrado
- **409 Conflict**: Canal com o mesmo ID já existe / Número WhatsApp já está em uso
- **500 Internal Server Error**: Erro interno do servidor
- **503 Service Unavailable**: Banco de dados não está habilitado

## Tipos de Canal Suportados

- `whatsapp`: WhatsApp Business API
- `instagram`: Instagram Direct
- `widget`: Widget web/chat
- `telegram`: Telegram Bot
- `sms`: SMS/Texto
- `email`: Email


## Validações Especiais

### Duplicidade de Números WhatsApp

Para canais do tipo `whatsapp`, o sistema verifica automaticamente se já existe outro canal **ativo** com o mesmo `whatsapp_phone_number`:

- **Na criação**: Não permite criar se já existir outro canal ativo com o mesmo número
- **Na atualização**: Não permite alterar para um número que já está em uso por outro canal ativo
- **Retorna erro 409** com detalhes do canal existente

#### Exemplo de Erro por Duplicidade:
```json
{
  "error": "Já existe um canal WhatsApp ativo com o número +5511999999999",
  "status": "error",
  "existing_channel": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "WhatsApp Vendas",
    "whatsapp_phone_number": "+5511999999999"
  }
}
```

## Segurança e Permissões

1. **Isolamento por Conta**: Usuários só podem acessar canais da própria conta
2. **Validação JWT**: Todos os endpoints requerem token válido
3. **Validação de UUID**: IDs são validados como UUID v4
4. **Sanitização**: Dados são sanitizados antes de armazenar
5. **Logs de Auditoria**: Todas as operações são logadas
6. **Validação de Duplicidade**: Números WhatsApp únicos por sistema

## Notas Importantes

1. **Account ID**: Extraído automaticamente do token JWT (`user_metadata.account_id`)
2. **Delete Permanente**: DELETE remove o canal completamente do banco de dados
3. **Config Flexível**: Campo `config` aceita qualquer estrutura JSON
4. **Relacionamentos**: `bot_id` pode referenciar bots existentes (opcional)
5. **Segurança**: Operações de DELETE são irreversíveis 