# API de Integrações

Este documento descreve a API para gerenciar integrações do sistema WhatsApp.

## Autenticação

Todos os endpoints requerem autenticação JWT. Inclua o token no header:
```
Authorization: Bearer <seu_jwt_token>
```

## Estrutura da Tabela Integrations

```sql
CREATE TABLE `integrations` (
  `id` varchar(36) NOT NULL,
  `account_id` varchar(36) NOT NULL,
  `integration_type` varchar(50) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `access_token` text,
  `client_id` text,
  `client_secret` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

## Endpoints

### 1. Listar Integrações

**GET** `/integrations`

Lista todas as integrações da conta autenticada.

#### Parâmetros de Query (Opcionais)
- `active_only` (string): "true" para filtrar apenas integrações ativas. Default: "false"

#### Resposta de Sucesso (200)
```json
{
  "integrations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "account_id": "550e8400-e29b-41d4-a716-446655440001",
      "integration_type": "whatsapp",
      "name": "WhatsApp Business",
      "is_active": 1,
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1,
  "status": "success"
}
```

#### Exemplo de Uso
```bash
curl -X GET "https://api.exemplo.com/integrations?active_only=true" \
  -H "Authorization: Bearer seu_jwt_token"
```

### 2. Criar Integração

**POST** `/integrations`

Cria uma nova integração.

#### Campos Obrigatórios
- `integration_type` (string): Tipo da integração

#### Campos Opcionais
- `name` (string): Nome da integração (máx. 100 chars)
- `is_active` (boolean/int): Status ativo (default: 1)
- `access_token` (string): Token de acesso
- `client_id` (string): ID do cliente
- `client_secret` (string): Secret do cliente

#### Exemplo de Requisição
```json
{
  "integration_type": "whatsapp",
  "name": "WhatsApp Business",
  "is_active": true,
  "access_token": "EAAG1...",

  "client_id": "123456789",
  "client_secret": "abcdef123456"
}
```

#### Resposta de Sucesso (201)
```json
{
  "integration": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "550e8400-e29b-41d4-a716-446655440001",
    "integration_type": "whatsapp",
    "name": "WhatsApp Business",
    "is_active": 1,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00",
    "access_token": "EAAG1...",
  
    "client_id": "123456789",
    "client_secret": "abcdef123456"
  },
  "message": "Integração criada com sucesso",
  "status": "success"
}
```

#### Exemplo de Uso
```bash
curl -X POST "https://api.exemplo.com/integrations" \
  -H "Authorization: Bearer seu_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "integration_type": "whatsapp",
    "name": "WhatsApp Business",
    "access_token": "EAAG1...",
  
  }'
```

### 3. Buscar Integração Específica

**GET** `/integrations/{integration_id}`

Busca uma integração específica pelo ID.

#### Parâmetros
- `integration_id` (UUID): ID da integração

#### Resposta de Sucesso (200)
```json
{
  "integration": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "550e8400-e29b-41d4-a716-446655440001",
    "integration_type": "whatsapp",
    "name": "WhatsApp Business",
    "is_active": 1,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00",
  
  },
  "status": "success"
}
```

#### Exemplo de Uso
```bash
curl -X GET "https://api.exemplo.com/integrations/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer seu_jwt_token"
```

### 4. Atualizar Integração

**PUT** `/integrations/{integration_id}`

Atualiza uma integração existente. Apenas os campos fornecidos são atualizados.

#### Parâmetros
- `integration_id` (UUID): ID da integração

#### Campos Opcionais (todos)
- `integration_type` (string): Tipo da integração
- `name` (string): Nome da integração (máx. 100 chars)
- `is_active` (boolean/int): Status ativo
- `access_token` (string): Token de acesso (usar `null` para limpar)
- `client_id` (string): ID do cliente (usar `null` para limpar)
- `client_secret` (string): Secret do cliente (usar `null` para limpar)

#### Exemplo de Requisição
```json
{
  "name": "WhatsApp Business Atualizado",
  "is_active": false,
  "access_token": null,

}
```

#### Resposta de Sucesso (200)
```json
{
  "integration": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "account_id": "550e8400-e29b-41d4-a716-446655440001",
    "integration_type": "whatsapp",
    "name": "WhatsApp Business Atualizado",
    "is_active": 0,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T11:45:00",
    "access_token": null,
  
    "client_id": "123456789",
    "client_secret": "abcdef123456"
  },
  "message": "Integração atualizada com sucesso",
  "status": "success"
}
```

#### Exemplo de Uso
```bash
curl -X PUT "https://api.exemplo.com/integrations/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer seu_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "WhatsApp Business Atualizado",
    "is_active": false
  }'
```

### 5. Excluir Integração

**DELETE** `/integrations/{integration_id}`

Remove uma integração.

#### Parâmetros
- `integration_id` (UUID): ID da integração

#### Resposta de Sucesso (200)
```json
{
  "message": "Integração removida com sucesso",
  "status": "success"
}
```

#### Exemplo de Uso
```bash
curl -X DELETE "https://api.exemplo.com/integrations/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer seu_jwt_token"
```

## Códigos de Status HTTP

### Sucesso
- **200** - OK: Operação realizada com sucesso
- **201** - Created: Integração criada com sucesso

### Erro do Cliente
- **400** - Bad Request: Dados inválidos ou malformados
- **401** - Unauthorized: Token JWT inválido ou ausente
- **403** - Forbidden: Acesso negado à integração
- **404** - Not Found: Integração não encontrada

### Erro do Servidor
- **500** - Internal Server Error: Erro interno do servidor
- **503** - Service Unavailable: Banco de dados não disponível

## Validações

### Campo `integration_type`
- **Obrigatório** para criação
- Deve ser uma string não vazia
- Máximo 50 caracteres

### Campo `name`
- **Opcional**
- Deve ser uma string
- Máximo 100 caracteres

### Campo `is_active`
- **Opcional** (default: 1)
- Aceita boolean (`true`/`false`) ou número (`0`/`1`)


### Campo `access_token`
- **Opcional**
- Deve ser uma string
- Usar `null` para limpar o valor

### Campo `client_id`
- **Opcional**
- Deve ser uma string
- Usar `null` para limpar o valor

### Campo `client_secret`
- **Opcional**
- Deve ser uma string
- Usar `null` para limpar o valor

### Validação de UUID
- O `integration_id` deve ser um UUID válido
- O campo `id` é gerado automaticamente no formato UUID v4

## Segurança e Permissões

### Proteção de Dados Sensíveis

**Campos retornados por endpoint:**

#### Endpoints GET (Lista e Individual) - APENAS dados não sensíveis:
- ✅ `id`, `account_id`, `integration_type`, `name`
- ✅ `is_active`, `created_at`, `updated_at`
- ❌ `access_token`, `client_id`, `client_secret` (removidos por segurança)

#### Endpoints POST/PUT (Criação e Atualização) - TODOS os campos:
- ✅ Incluem **todos os campos**, incluindo os sensíveis
- ✅ Permitem criar/atualizar campos sensíveis
- ✅ Retornam a integração completa após a operação

**Justificativa:** Campos sensíveis não devem trafegar desnecessariamente pela rede durante consultas.

### Isolamento por Conta
- Cada usuário só pode acessar integrações da sua própria conta
- O `account_id` é extraído automaticamente do token JWT
- Tentativas de acesso a integrações de outras contas retornam erro 403

### Validação de Propriedade
- Operações de GET, PUT e DELETE verificam se a integração pertence à conta do usuário
- Integração não encontrada ou de outra conta retorna erro 404 ou 403

### Logs de Auditoria
- Todas as operações são registradas nos logs
- Inclui informações de segurança e validação de isolamento

## Exemplos de Respostas de Erro

### Token JWT Inválido (401)
```json
{
  "error": "Token JWT não contém account_id válido",
  "status": "error"
}
```

### Campo Obrigatório Ausente (400)
```json
{
  "error": "Campo obrigatório 'integration_type' não fornecido",
  "status": "error"
}
```

### UUID Inválido (400)
```json
{
  "error": "ID da integração deve ser um UUID válido",
  "status": "error"
}
```

### Integração Não Encontrada (404)
```json
{
  "error": "Integração não encontrada",
  "status": "error"
}
```

### Acesso Negado (403)
```json
{
  "error": "Acesso negado à integração",
  "status": "error"
}
```

### Banco Indisponível (503)
```json
{
  "error": "Banco de dados não está habilitado",
  "status": "error"
}
```

## Tipos de Integração Sugeridos

Embora o campo `integration_type` aceite qualquer string, aqui estão algumas sugestões:

- `whatsapp` - WhatsApp Business API
- `instagram` - Instagram API
- `facebook` - Facebook API
- `telegram` - Telegram Bot API
- `webhook` - Webhook personalizado
- `email` - Integração de email
- `sms` - Integração SMS
- `chatbot` - Chatbot personalizado

## Versionamento

**Versão Atual:** 1.0  
**Última Atualização:** Janeiro 2024

## Suporte

Para dúvidas sobre a API de Integrações, consulte a documentação do sistema ou entre em contato com o suporte técnico.