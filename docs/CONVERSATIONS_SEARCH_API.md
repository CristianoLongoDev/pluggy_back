# API de Pesquisa de Conversas

Esta API permite pesquisar conversas por termos contidos nas mensagens, facilitando a busca de conversas específicas baseadas no conteúdo das mensagens.

## Endpoint

**POST** `/api/conversations/search`

## Autenticação

Esta API requer autenticação via JWT token no header `Authorization`:

```
Authorization: Bearer <jwt_token>
```

## Parâmetros da Requisição

### Body (JSON)

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `search_term` | string | ✅ | Termo de busca (mínimo 3 caracteres) |
| `limit` | integer | ❌ | Número máximo de resultados (padrão: 50, máximo: 100) |
| `offset` | integer | ❌ | Número de registros para pular (padrão: 0) |
| `account_id` | string | ❌ | ID da conta para filtrar resultados |

### Exemplo de Requisição

```json
{
  "search_term": "relatorio contabil",
  "limit": 25,
  "offset": 0,
  "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136"
}
```

## Funcionalidade da Busca

### Como Funciona

1. **Busca por Palavras**: O sistema quebra o `search_term` por espaços e busca por **TODAS** as palavras nas mensagens
2. **Exemplo**: `"relatorio contabil"` → busca mensagens que contenham **"relatorio"** E **"contabil"**
3. **Case Insensitive**: A busca não diferencia maiúsculas de minúsculas
4. **Busca Parcial**: Usa `LIKE %termo%` para encontrar palavras dentro do texto

### SQL Equivalente

```sql
SELECT DISTINCT conversation.*
FROM conversation_message 
WHERE message_text LIKE '%relatorio%' 
  AND message_text LIKE '%contabil%'
```

## Resposta da API

### Sucesso (200 OK)

```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "conversation_id": 154,
        "contact_id": "2e7b013b-7795-48be-a28b-1e820f8ac239",
        "status": "closed",
        "started_at": "2025-08-21T14:36:16",
        "ended_at": "2025-08-21T14:38:36",
        "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
        "contact_name": "Cristiano",
        "contact_phone": "555496598592",
        "account_name": "Intelectivo Sistemas",
        "total_messages": 5,
        "last_message_at": "2025-08-21T14:37:20",
        "message_preview": "nao tem mais muita informação .. so diz que é invalido | nao estou conseguindo logar no plugger diz senha invalida | pode me ajudar com um problema"
      }
    ],
    "pagination": {
      "total": 1,
      "limit": 25,
      "offset": 0,
      "has_next": false
    },
    "search_info": {
      "term": "relatorio contabil",
      "results_count": 1
    }
  },
  "status": "success"
}
```

### Campos da Conversa

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `conversation_id` | integer | ID único da conversa |
| `contact_id` | string | ID do contato |
| `status` | string | Status da conversa (active, closed, etc.) |
| `started_at` | datetime | Data/hora de início da conversa |
| `ended_at` | datetime | Data/hora de fim da conversa (se fechada) |
| `account_id` | string | ID da conta proprietária |
| `contact_name` | string | Nome do contato |
| `contact_phone` | string | Telefone do contato |
| `account_name` | string | Nome da conta |
| `total_messages` | integer | Número total de mensagens na conversa |
| `last_message_at` | datetime | Data/hora da última mensagem |
| `message_preview` | string | Preview das mensagens (até 100 chars cada, separadas por " \| ") |

### Paginação

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total` | integer | Total de conversas encontradas |
| `limit` | integer | Limite usado na busca |
| `offset` | integer | Offset usado na busca |
| `has_next` | boolean | Se há mais resultados disponíveis |

## Erros Possíveis

### 400 - Bad Request

```json
{
  "error": "Campo 'search_term' é obrigatório",
  "status": "error"
}
```

```json
{
  "error": "Termo de busca deve ter pelo menos 3 caracteres",
  "status": "error"
}
```

### 401 - Unauthorized

```json
{
  "error": "Token não fornecido",
  "status": "error"
}
```

### 503 - Service Unavailable

```json
{
  "error": "Banco de dados não está habilitado",
  "status": "error"
}
```

### 500 - Internal Server Error

```json
{
  "error": "Erro interno: <descrição do erro>",
  "status": "error"
}
```

## Exemplos de Uso

### 1. Busca Simples

```bash
curl -X POST http://localhost:5000/api/conversations/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{
    "search_term": "relatorio"
  }'
```

### 2. Busca com Múltiplas Palavras

```bash
curl -X POST http://localhost:5000/api/conversations/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{
    "search_term": "problema senha",
    "limit": 10
  }'
```

### 3. Busca com Paginação

```bash
curl -X POST http://localhost:5000/api/conversations/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{
    "search_term": "ticket",
    "limit": 20,
    "offset": 40
  }'
```

### 4. Busca Filtrada por Conta

```bash
curl -X POST http://localhost:5000/api/conversations/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{
    "search_term": "atendimento",
    "account_id": "3d0477ad-537b-4364-94bd-cd46acec2136",
    "limit": 50
  }'
```

## JavaScript/Frontend

### Exemplo com Fetch

```javascript
async function searchConversations(searchTerm, options = {}) {
  const token = localStorage.getItem('jwt_token');
  
  const body = {
    search_term: searchTerm,
    limit: options.limit || 50,
    offset: options.offset || 0
  };
  
  if (options.accountId) {
    body.account_id = options.accountId;
  }
  
  try {
    const response = await fetch('/api/conversations/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(body)
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Erro na pesquisa');
    }
    
    return data.data;
  } catch (error) {
    console.error('Erro ao pesquisar conversas:', error);
    throw error;
  }
}

// Uso
searchConversations('relatorio contabil', { limit: 25 })
  .then(result => {
    console.log('Conversas encontradas:', result.conversations);
    console.log('Total:', result.pagination.total);
  })
  .catch(error => {
    console.error('Erro:', error);
  });
```

### Exemplo com React

```jsx
import { useState, useEffect } from 'react';

function ConversationSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({});

  const handleSearch = async (e) => {
    e.preventDefault();
    if (searchTerm.length < 3) return;

    setLoading(true);
    try {
      const result = await searchConversations(searchTerm);
      setConversations(result.conversations);
      setPagination(result.pagination);
    } catch (error) {
      alert('Erro na pesquisa: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSearch}>
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Digite pelo menos 3 caracteres..."
          minLength={3}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Pesquisando...' : 'Pesquisar'}
        </button>
      </form>

      <div>
        <h3>Resultados ({pagination.total || 0})</h3>
        {conversations.map(conv => (
          <div key={conv.conversation_id}>
            <h4>{conv.contact_name} - {conv.contact_phone}</h4>
            <p><strong>Conversa #{conv.conversation_id}</strong></p>
            <p><small>{conv.message_preview}</small></p>
            <p><em>Última mensagem: {new Date(conv.last_message_at).toLocaleString()}</em></p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## Performance e Limitações

### Otimizações Implementadas

1. **DISTINCT**: Evita conversas duplicadas
2. **LIMIT/OFFSET**: Paginação para performance
3. **Índices**: Recomenda-se criar índices em `conversation_message.message_text`
4. **Preview**: Limitado a 100 caracteres por mensagem

### Limitações

1. **Máximo 100 resultados** por página
2. **Busca literal**: Não suporta regex ou busca semântica
3. **Ordem fixa**: Sempre ordena pela última mensagem (mais recente primeiro)

### Recomendações de Índices

```sql
-- Índice para otimizar a busca em mensagens
CREATE INDEX idx_conversation_message_text ON conversation_message(message_text);

-- Índice composto para filtros por conta
CREATE INDEX idx_conversation_account_timestamp ON conversation(account_id, started_at);
```

## Casos de Uso

### Frontend - Lista de Conversas

- **Busca rápida**: Usuário digita termo e vê conversas relacionadas
- **Paginação**: Navegar pelos resultados sem sobrecarregar a interface
- **Filtros**: Filtrar por conta para usuários multi-tenant

### Análise de Dados

- **Buscar temas**: Encontrar conversas sobre "problemas", "reclamações", etc.
- **Análise de produtos**: Buscar menções a produtos específicos
- **Suporte**: Localizar conversas sobre bugs ou dificuldades

### Auditoria

- **Compliance**: Buscar conversas contendo termos específicos
- **Relatórios**: Extrair conversas para análise externa
