# API de Contas - Documentação

Esta documentação descreve como usar os endpoints para gerenciar contas na aplicação WhatsApp.

## Endpoints Disponíveis

### 1. Criar Nova Conta
**POST** `/accounts`

Cria uma nova conta no sistema.

#### Corpo da Requisição
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Nome da Conta"
}
```

#### Campos Obrigatórios
- `id`: UUID v4 válido (gerado no front-end)
- `name`: Nome da conta (máximo 100 caracteres)

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Conta criada com sucesso",
  "status": "success",
  "account": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Nome da Conta",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

#### Exemplo de Resposta (Erro - 400)
```json
{
  "error": "Campo 'id' é obrigatório",
  "status": "error"
}
```

#### Exemplo de Resposta (Conflito - 409)
```json
{
  "error": "Conta com este ID já existe",
  "status": "error",
  "existing_account": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Nome Existente",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

### 2. Buscar Conta por ID (Autenticação Obrigatória)
**GET** `/accounts/{account_id}`

Busca uma conta específica pelo seu ID. **Requer autenticação JWT.**

#### Parâmetros da URL
- `account_id`: UUID da conta a ser buscada

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Autenticação
Este endpoint requer um token JWT válido do Supabase no header Authorization:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "account": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Nome da Conta",
    "created_at": "2024-01-15T10:30:00"
  },
  "authenticated_user": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "usuario@exemplo.com",
    "role": "user"
  }
}
```

#### Exemplo de Resposta (Não Autorizado - 401)
```json
{
  "error": "Token de autorização é obrigatório",
  "status": "error"
}
```

```json
{
  "error": "Token inválido ou expirado",
  "status": "error"
}
```

#### Exemplo de Resposta (Não Encontrado - 404)
```json
{
  "error": "Conta não encontrada",
  "status": "error"
}
```

## Exemplos de Uso

### Usando cURL

#### Criar uma nova conta:
```bash
curl -X POST http://localhost:5000/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Minha Conta de Teste"
  }'
```

#### Buscar uma conta (com autenticação):
```bash
curl -X GET http://localhost:5000/accounts/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### Usando JavaScript (Frontend)

#### Criar uma nova conta:
```javascript
// Gerar UUID v4 no frontend
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

async function createAccount(name) {
  const accountData = {
    id: generateUUID(),
    name: name
  };

  try {
    const response = await fetch('/accounts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(accountData)
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Conta criada:', result.account);
      return result.account;
    } else {
      console.error('Erro ao criar conta:', result.error);
      throw new Error(result.error);
    }
  } catch (error) {
    console.error('Erro na requisição:', error);
    throw error;
  }
}

// Usar a função
createAccount('Nome da Minha Conta')
  .then(account => console.log('Sucesso:', account))
  .catch(error => console.error('Falha:', error));
```

#### Buscar uma conta (com autenticação):
```javascript
async function getAccount(accountId, jwtToken) {
  try {
    const response = await fetch(`/accounts/${accountId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    const result = await response.json();
    
    if (response.ok) {
      console.log('Conta encontrada:', result.account);
      console.log('Usuário autenticado:', result.authenticated_user);
      return result;
    } else {
      console.error('Erro ao buscar conta:', result.error);
      return null;
    }
  } catch (error) {
    console.error('Erro na requisição:', error);
    return null;
  }
}

// Exemplo de uso com token do Supabase
const supabaseToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."; // Token do Supabase
getAccount('550e8400-e29b-41d4-a716-446655440000', supabaseToken)
  .then(result => {
    if (result) {
      console.log('Sucesso:', result);
    }
  })
  .catch(error => console.error('Falha:', error));
```

## Códigos de Status HTTP

- **200 OK**: Conta encontrada com sucesso
- **201 Created**: Conta criada com sucesso
- **400 Bad Request**: Dados inválidos ou ausentes
- **401 Unauthorized**: Token JWT ausente, inválido ou expirado
- **404 Not Found**: Conta não encontrada
- **409 Conflict**: Conta com o mesmo ID já existe
- **500 Internal Server Error**: Erro interno do servidor
- **503 Service Unavailable**: Banco de dados não está habilitado

## Notas Importantes

1. **UUID Generation**: O UUID deve ser gerado no frontend para garantir unicidade
2. **Validação**: O sistema valida se o ID fornecido é um UUID válido
3. **Duplicatas**: O sistema previne a criação de contas com IDs duplicados
4. **Database**: Os endpoints só funcionam se o banco de dados estiver habilitado
5. **Logging**: Todas as operações são logadas para auditoria
6. **Autenticação JWT**: O endpoint GET requer token JWT válido do Supabase
7. **Token Format**: Use o formato "Bearer <token>" no header Authorization
8. **Supabase Config**: Configure SUPABASE_URL (nova API com JWT Signing Keys)

## Configuração do Supabase (Nova API - JWT Signing Keys)

A aplicação agora usa a **nova API de JWT Signing Keys** do Supabase, que é mais segura que o JWT Secret legacy.

### Variáveis necessárias:

1. **SUPABASE_URL**: URL do seu projeto Supabase (https://seu-projeto.supabase.co)
2. **SUPABASE_ANON_KEY**: Chave anônima do projeto (opcional)

### ✅ Vantagens da nova abordagem:

- **Mais segura**: Usa chaves públicas RSA/ECDSA ao invés de secrets compartilhados
- **Rotação automática**: Supabase gerencia a rotação das chaves
- **Sem secrets**: Não precisa do JWT secret na aplicação
- **Cache inteligente**: Sistema de cache das chaves públicas

### Para configurar no Kubernetes:

```bash
# Encode apenas a URL e chave anônima em base64
echo -n "https://seu-projeto.supabase.co" | base64  
echo -n "sua_anon_key_aqui" | base64

# Atualize k8s/secret.yaml com os valores encodados
# Não precisa mais do SUPABASE_JWT_SECRET!
```

### Endpoints de teste:

```bash
# Verificar configuração JWT (público)
curl https://atendimento.pluggerbi.com/auth/jwt/status

# Testar autenticação JWT (requer token)
curl -X POST https://atendimento.pluggerbi.com/auth/jwt/test \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Como funciona:

1. **Token JWT** é criado pelo Supabase com assinatura RSA/ECDSA
2. **Aplicação busca** chaves públicas do endpoint `/auth/v1/jwks`
3. **Validação** usando a chave pública correspondente ao `kid` do token
4. **Cache** das chaves públicas por 1 hora para performance 