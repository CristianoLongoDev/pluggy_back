# API de Ações de Funções de Bots - Documentação

Esta documentação descreve como usar o endpoint para listar as ações disponíveis para funções de bots.

## 🔒 Autenticação

**O endpoint requer autenticação JWT válida**. O `account_id` é extraído automaticamente do token JWT do usuário.

```
Authorization: Bearer SEU_TOKEN_JWT_DO_SUPABASE
```

## Endpoint Disponível

### Listar Ações de Funções de Bots
**GET** `/bots/functions/actions`

Lista todas as ações disponíveis para funções de bots, com opção de filtrar por tipo de integração.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros de Query (Opcionais)
- `integration_type`: Filtrar ações por tipo de integração específica (ex: `movidesk`, `chatgpt`, etc.)

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "actions": [
    {
      "id": 1,
      "action": "create_ticket",
      "name": "Criar Ticket",
      "integration_type": "movidesk"
    },
    {
      "id": 2,
      "action": "search_knowledge",
      "name": "Buscar Conhecimento",
      "integration_type": "chatgpt"
    },
    {
      "id": 3,
      "action": "send_email",
      "name": "Enviar Email",
      "integration_type": null
    }
  ],
  "total": 3,
  "filter": {
    "integration_type": null
  }
}
```

#### Exemplo de Resposta Filtrada
**GET** `/bots/functions/actions?integration_type=movidesk`

```json
{
  "status": "success",
  "actions": [
    {
      "id": 1,
      "action": "create_ticket",
      "name": "Criar Ticket",
      "integration_type": "movidesk"
    },
    {
      "id": 4,
      "action": "update_ticket",
      "name": "Atualizar Ticket",
      "integration_type": "movidesk"
    }
  ],
  "total": 2,
  "filter": {
    "integration_type": "movidesk"
  }
}
```

## Estrutura da Tabela

```sql
CREATE TABLE `bots_functions_actions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action` varchar(45) DEFAULT NULL,
  `name` varchar(45) DEFAULT NULL,
  `integration_type` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

### Campos da Tabela
- **`id`**: Identificador único da ação (auto incremento)
- **`action`**: Código/nome da ação (ex: `create_ticket`, `send_email`)
- **`name`**: Nome amigável da ação (ex: "Criar Ticket", "Enviar Email")  
- **`integration_type`**: Tipo de integração (ex: `movidesk`, `chatgpt`, `null` para genérica)

## Exemplos de Uso

### Usando cURL

#### Listar todas as ações:
```bash
curl -X GET https://atendimento.pluggerbi.com/bots/functions/actions \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

#### Listar ações específicas de uma integração:
```bash
curl -X GET "https://atendimento.pluggerbi.com/bots/functions/actions?integration_type=movidesk" \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Usando JavaScript (Frontend)

#### Listar todas as ações:
```javascript
async function getBotsFunctionsActions(jwtToken, integrationTypeFilter = null) {
  try {
    let url = '/bots/functions/actions';
    if (integrationTypeFilter) {
      url += `?integration_type=${encodeURIComponent(integrationTypeFilter)}`;
    }
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    
    if (response.ok) {
      console.log('Ações disponíveis:', result.actions);
      console.log('Total:', result.total);
      return result.actions;
    } else {
      console.error('Erro:', result.error);
      return null;
    }
  } catch (error) {
    console.error('Erro na requisição:', error);
    return null;
  }
}

// Exemplos de uso
getBotsFunctionsActions(jwtToken)
  .then(actions => console.log('Todas as ações:', actions));

getBotsFunctionsActions(jwtToken, 'movidesk')
  .then(actions => console.log('Ações do Movidesk:', actions));
```

## Códigos de Status HTTP

- **200 OK**: Ações listadas com sucesso
- **400 Bad Request**: Token JWT sem account_id válido
- **401 Unauthorized**: Token JWT ausente, inválido ou expirado
- **500 Internal Server Error**: Erro interno do servidor
- **503 Service Unavailable**: Banco de dados não está habilitado

## Casos de Uso

### 1. **Listagem para Interface de Criação de Funções**
Usado para popular dropdowns ou listas de ações disponíveis quando o usuário está criando funções para bots.

### 2. **Filtrar por Tipo de Integração**
Quando o usuário seleciona uma integração específica (ex: Movidesk), mostra apenas as ações compatíveis com essa integração.

### 3. **Validação de Ações**
Verificar se uma ação específica existe e é válida antes de criar uma função de bot.

## Segurança e Logs

- **Autenticação**: Requer token JWT válido
- **Logs de Auditoria**: Registra quem acessou as ações e quando
- **Filtros**: Suporte a filtros por tipo de integração
- **Isolamento**: Embora os dados sejam globais, o acesso é controlado por autenticação

## Notas Importantes

1. **Dados Globais**: Esta tabela contém dados de referência globais (não por conta)
2. **Filtros Opcionais**: O parâmetro `integration_type` permite filtrar resultados
3. **Ordenação**: Resultados são ordenados por `integration_type` e depois por `name`
4. **Valores NULL**: `integration_type` pode ser NULL para ações genéricas
5. **Cache**: Considere implementar cache no frontend pois estes dados mudam raramente

## Integração com Outros Endpoints

Este endpoint é tipicamente usado em conjunto com:
- **Criação de Funções**: `/bots/{bot_id}/functions` (POST)
- **Listagem de Integrações**: Para obter tipos de integração disponíveis
- **Gerenciamento de Bots**: Para configurar funcionalidades específicas por integração
