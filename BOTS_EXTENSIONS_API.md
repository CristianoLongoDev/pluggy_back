# API de Extensões de Bots - Documentação

Esta documentação descreve os endpoints para gerenciar **prompts**, **funções** e **parâmetros de funções** dos bots na aplicação WhatsApp.

## 🔒 Autenticação

**TODOS os endpoints requerem autenticação JWT válida**. O `account_id` é extraído automaticamente do token JWT do usuário.

```
Authorization: Bearer SEU_TOKEN_JWT_DO_SUPABASE
```

## 📝 Estrutura das Tabelas

### bots_prompts
```sql
CREATE TABLE `bots_prompts` (
  `bot_id` varchar(36) NOT NULL,
  `id` varchar(36) NOT NULL COMMENT 'UUID do prompt',
  `prompt` text NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `rule_display` varchar(30) DEFAULT NULL COMMENT 'first contact, every time, email not informed',
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`bot_id`,`id`)
);
```

### bots_functions
```sql
CREATE TABLE `bots_functions` (
  `bot_id` varchar(36) NOT NULL,
  `function_id` varchar(150) NOT NULL COMMENT 'Nome interno da função',
  `description` varchar(255) DEFAULT NULL,
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`bot_id`,`function_id`)
);
```

### bots_functions_parameters
```sql
CREATE TABLE `bots_functions_parameters` (
  `function_id` varchar(150) NOT NULL,
  `parameter_id` varchar(100) NOT NULL COMMENT 'Nome do parâmetro',
  `type` varchar(20) NOT NULL COMMENT 'string,number,integer,boolean,object,array',
  `permited_values` text,
  `default_value` varchar(100) DEFAULT NULL,
  `format` varchar(15) DEFAULT NULL COMMENT 'email, uri, date, date-time',
  `description` text DEFAULT NULL,
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`function_id`,`parameter_id`)
);
```

---

# 📝 Endpoints de Prompts

Os prompts são textos acessórios usados dinamicamente durante a interação do bot.

## 1. Listar Prompts de um Bot
**GET** `/bots/{bot_id}/prompts`

Lista todos os prompts de um bot específico.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase

#### Parâmetros da URL
- `bot_id`: UUID do bot

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "prompts": [
    {
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "prompt": "Olá! Bem-vindo ao nosso atendimento. Como posso ajudá-lo hoje?",
      "description": "Mensagem de boas-vindas padrão",
      "rule_display": "first contact",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1
}
```

## 2. Criar Prompt
**POST** `/bots/{bot_id}/prompts`

Cria um novo prompt para um bot específico.

#### Headers Obrigatórios
- `Authorization`: Bearer token JWT do Supabase
- `Content-Type`: application/json

#### Corpo da Requisição
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "prompt": "Olá! Bem-vindo ao nosso atendimento. Como posso ajudá-lo hoje?",
  "description": "Mensagem de boas-vindas padrão",
  "rule_display": "first contact"
}
```

#### Campos Obrigatórios
- `id`: UUID v4 único do prompt
- `prompt`: Texto do prompt (tipo TEXT)

#### Campos Opcionais
- `description`: Descrição do prompt (máximo 255 caracteres)
- `rule_display`: Regra de exibição (`first contact`, `every time`, `email not informed`)

#### Opções do Campo rule_display
- `first contact`: O prompt será exibido apenas no primeiro contato com o usuário
- `every time`: O prompt será exibido em todas as interações
- `email not informed`: O prompt será exibido quando o usuário não informou email

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Prompt criado com sucesso",
  "status": "success",
  "prompt": {
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "prompt": "Olá! Bem-vindo ao nosso atendimento. Como posso ajudá-lo hoje?",
    "description": "Mensagem de boas-vindas padrão",
    "rule_display": "first contact",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
}
```

## 3. Atualizar Prompt
**PUT** `/bots/{bot_id}/prompts/{prompt_id}`

Atualiza um prompt específico. Apenas os campos fornecidos são atualizados.

#### Corpo da Requisição (Todos os campos são opcionais)
```json
{
  "prompt": "Olá! Bem-vindo ao nosso atendimento automatizado. Como posso ajudá-lo hoje?",
  "description": "Mensagem de boas-vindas atualizada",
  "rule_display": "every time"
}
```

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Prompt atualizado com sucesso",
  "status": "success",
  "prompt": {
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "prompt": "Olá! Bem-vindo ao nosso atendimento automatizado. Como posso ajudá-lo hoje?",
    "description": "Mensagem de boas-vindas atualizada",
    "rule_display": "every time",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T11:45:00"
  },
  "updated_fields": ["prompt", "description", "rule_display"]
}
```

## 4. Deletar Prompt
**DELETE** `/bots/{bot_id}/prompts/{prompt_id}`

Deleta permanentemente um prompt específico.

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Prompt deletado permanentemente com sucesso",
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "prompt_id": "123e4567-e89b-12d3-a456-426614174000",
  "action": "deletado permanentemente"
}
```

---

# ⚙️ Endpoints de Funções

As funções definem capacidades específicas que o bot pode executar.

## 1. Listar Funções de um Bot
**GET** `/bots/{bot_id}/functions`

Lista todas as funções de um bot específico.

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "functions": [
    {
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "function_id": "buscar_produto",
      "description": "Buscar informações de produtos no catálogo",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1
}
```

## 2. Listar Funções com Status de Uso
**GET** `/bots/{bot_id}/functions/used`

Lista todas as funções de um bot específico mostrando como estão sendo usadas (se associadas a prompts ou diretamente ao bot).

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "functions": [
    {
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "function_id": "buscar_produto",
      "description": "Buscar informações de produtos no catálogo",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00",
      "used": "bot"
    },
    {
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "function_id": "processar_pagamento",
      "description": "Processar pagamentos de pedidos",
      "created_at": "2024-01-15T11:00:00",
      "updated_at": "2024-01-15T11:00:00",
      "used": "prompt"
    },
    {
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "function_id": "calcular_frete",
      "description": "Calcular valor do frete",
      "created_at": "2024-01-15T12:00:00",
      "updated_at": "2024-01-15T12:00:00",
      "used": null
    }
  ],
  "total": 3
}
```

#### Campo `used`
- **`"bot"`**: Função está associada diretamente ao bot (sempre executada)
- **`"prompt"`**: Função está associada a um ou mais prompts específicos
- **`null`**: Função está definida mas não está sendo usada em nenhum lugar

#### Exemplo de Uso
```bash
curl -X GET "https://api.exemplo.com/bots/550e8400-e29b-41d4-a716-446655440000/functions/used" \
  -H "Authorization: Bearer seu_jwt_token"
```

## 3. Criar Função
**POST** `/bots/{bot_id}/functions`

Cria uma nova função para um bot específico.

#### Corpo da Requisição
```json
{
  "function_id": "buscar_produto",
  "description": "Buscar informações de produtos no catálogo"
}
```

#### Campos Obrigatórios
- `function_id`: Nome interno da função (máximo 150 caracteres)

#### Campos Opcionais
- `description`: Descrição da função (máximo 255 caracteres)

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Função criada com sucesso",
  "status": "success",
  "function": {
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "function_id": "buscar_produto",
    "description": "Buscar informações de produtos no catálogo",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
}
```

## 4. Atualizar Função
**PUT** `/bots/{bot_id}/functions/{function_id}`

Atualiza uma função específica. Apenas os campos fornecidos são atualizados.

#### Corpo da Requisição (Todos os campos são opcionais)
```json
{
  "description": "Buscar informações detalhadas de produtos no catálogo com filtros avançados"
}
```

## 5. Deletar Função
**DELETE** `/bots/{bot_id}/functions/{function_id}`

Deleta permanentemente uma função específica e todos os seus parâmetros.

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Função e seus parâmetros deletados permanentemente com sucesso",
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "function_id": "buscar_produto",
  "action": "deletado permanentemente"
}
```

---

# 🔧 Endpoints de Parâmetros de Funções

Os parâmetros definem os dados de entrada necessários para executar uma função.

## 1. Listar Parâmetros de uma Função
**GET** `/bots/{bot_id}/functions/{function_id}/parameters`

Lista todos os parâmetros de uma função específica.

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "function_id": "buscar_produto",
  "parameters": [
    {
      "function_id": "buscar_produto",
      "parameter_id": "categoria",
      "type": "string",
      "permited_values": "[\"eletronicos\", \"roupas\", \"casa\"]",
      "default_value": "eletronicos",
      "format": null,
      "description": "Categoria do produto a ser buscado",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1
}
```

## 2. Criar Parâmetro(s)
**POST** `/bots/{bot_id}/functions/{function_id}/parameters`

Cria um ou múltiplos parâmetros para uma função específica. Aceita tanto um objeto único quanto um array de parâmetros.

### 2.1. Criar Parâmetro Único

#### Corpo da Requisição (Objeto único)
```json
{
  "parameter_id": "categoria",
  "type": "string",
  "permited_values": "[\"eletronicos\", \"roupas\", \"casa\"]",
  "default_value": "eletronicos",
  "format": null,
  "description": "Categoria do produto a ser buscado"
}
```

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Parâmetro criado com sucesso",
  "status": "success",
  "parameter": {
    "function_id": "buscar_produto",
    "parameter_id": "categoria",
    "type": "string",
    "permited_values": "[\"eletronicos\", \"roupas\", \"casa\"]",
    "default_value": "eletronicos",
    "format": null,
    "description": "Categoria do produto a ser buscado",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
}
```

### 2.2. Criar Múltiplos Parâmetros (Batch)

#### Corpo da Requisição (Array de objetos)
```json
[
  {
    "parameter_id": "categoria",
    "type": "string",
    "permited_values": "[\"eletronicos\", \"roupas\", \"casa\"]",
    "default_value": "eletronicos",
    "description": "Categoria do produto a ser buscado"
  },
  {
    "parameter_id": "preco_max",
    "type": "number",
    "default_value": "1000",
    "description": "Preço máximo do produto"
  },
  {
    "parameter_id": "disponivel",
    "type": "boolean",
    "default_value": "true",
    "description": "Mostrar apenas produtos disponíveis"
  }
]
```

#### Exemplo de Resposta (Sucesso Total - 201)
```json
{
  "message": "3 parâmetros criados com sucesso",
  "status": "success",
  "parameters": [
    {
      "function_id": "buscar_produto",
      "parameter_id": "categoria",
      "type": "string",
      "permited_values": "[\"eletronicos\", \"roupas\", \"casa\"]",
      "default_value": "eletronicos",
      "description": "Categoria do produto a ser buscado",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    },
    {
      "function_id": "buscar_produto",
      "parameter_id": "preco_max",
      "type": "number",
      "default_value": "1000",
      "description": "Preço máximo do produto",
      "created_at": "2024-01-15T10:30:01",
      "updated_at": "2024-01-15T10:30:01"
    },
    {
      "function_id": "buscar_produto",
      "parameter_id": "disponivel",
      "type": "boolean",
      "default_value": "true",
      "description": "Mostrar apenas produtos disponíveis",
      "created_at": "2024-01-15T10:30:02",
      "updated_at": "2024-01-15T10:30:02"
    }
  ],
  "total_created": 3
}
```

#### Exemplo de Resposta (Sucesso Parcial - 207)
```json
{
  "error": "Falha ao criar alguns parâmetros: preco_max",
  "status": "partial_error",
  "created_parameters": [
    {
      "function_id": "buscar_produto",
      "parameter_id": "categoria",
      "type": "string",
      "description": "Categoria do produto a ser buscado",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "failed_parameters": ["preco_max"],
  "total_created": 1,
  "total_failed": 1
}
```

#### 💡 Vantagens do Batch Insert
- **Eficiência**: Cria múltiplos parâmetros em uma única requisição
- **Atomicidade**: Valida todos os parâmetros antes de inserir qualquer um
- **Performance**: Reduz latência e overhead de múltiplas requisições
- **Feedback detalhado**: Relatório completo de sucessos e falhas

#### Códigos de Status HTTP
- **201**: Todos os parâmetros criados com sucesso
- **207**: Sucesso parcial (alguns parâmetros falharam)
- **400**: Erro de validação em requisição única ou lista vazia
- **409**: Parâmetro já existe (apenas em requisição única)

#### Campos Obrigatórios
- `parameter_id`: Nome do parâmetro (máximo 100 caracteres)
- `type`: Tipo do parâmetro (`string`, `number`, `integer`, `boolean`, `object`, `array`)

#### Campos Opcionais
- `permited_values`: Valores permitidos (texto JSON)
- `description`: Descrição do parâmetro (campo TEXT)
- `default_value`: Valor padrão (máximo 100 caracteres)
- `format`: Formato específico (`email`, `uri`, `date`, `date-time`)

## 3. Atualizar Parâmetro
**PUT** `/bots/{bot_id}/functions/{function_id}/parameters/{parameter_id}`

Atualiza um parâmetro específico. Apenas os campos fornecidos são atualizados.

#### Corpo da Requisição (Todos os campos são opcionais)
```json
{
  "type": "string",
  "permited_values": "[\"eletronicos\", \"roupas\", \"casa\", \"jardim\"]",
  "default_value": "casa",
  "description": "Categoria do produto a ser buscado com opções expandidas"
}
```

## 4. Atualizar Múltiplos Parâmetros (Batch)
**PUT** `/bots/{bot_id}/functions/{function_id}/parameters`

Atualiza múltiplos parâmetros de uma função específica em uma única requisição. Aceita um array de objetos de parâmetros.

#### Corpo da Requisição (Array de objetos)
```json
[
  {
    "parameter_id": "categoria",
    "type": "string",
    "permited_values": "[\"eletronicos\", \"roupas\", \"casa\", \"jardim\"]",
    "description": "Categoria atualizada com mais opções"
  },
  {
    "parameter_id": "preco_max",
    "default_value": "2000",
    "description": "Preço máximo aumentado"
  },
  {
    "parameter_id": "disponivel",
    "type": "boolean",
    "default_value": "false"
  }
]
```

#### Campos Obrigatórios
- `parameter_id`: Nome do parâmetro a ser atualizado

#### Campos Opcionais
- `type`, `permited_values`, `default_value`, `format`, `description`: Campos a serem atualizados

#### Exemplo de Resposta (Sucesso Total - 200)
```json
{
  "message": "3 parâmetros atualizados com sucesso",
  "status": "success",
  "parameters": [
    {
      "function_id": "buscar_produto",
      "parameter_id": "categoria",
      "type": "string",
      "permited_values": "[\"eletronicos\", \"roupas\", \"casa\", \"jardim\"]",
      "description": "Categoria atualizada com mais opções",
      "updated_at": "2024-01-15T10:35:00"
    }
  ],
  "total_updated": 3
}
```

#### Exemplo de Resposta (Sucesso Parcial - 207)
```json
{
  "error": "Falha ao atualizar alguns parâmetros: preco_max",
  "status": "partial_error",
  "updated_parameters": [
    {
      "function_id": "buscar_produto",
      "parameter_id": "categoria",
      "type": "string",
      "description": "Categoria atualizada",
      "updated_at": "2024-01-15T10:35:00"
    }
  ],
  "failed_parameters": ["preco_max"],
  "total_updated": 1,
  "total_failed": 1
}
```

## 5. Deletar Parâmetro
**DELETE** `/bots/{bot_id}/functions/{function_id}/parameters/{parameter_id}`

Deleta permanentemente um parâmetro específico.

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Parâmetro deletado permanentemente com sucesso",
  "status": "success",
  "function_id": "buscar_produto",
  "parameter_id": "categoria",
  "action": "deletado permanentemente"
}
```

## 6. Deletar Múltiplos Parâmetros (Batch)
**DELETE** `/bots/{bot_id}/functions/{function_id}/parameters`

Deleta múltiplos parâmetros de uma função específica em uma única requisição. Aceita formatos flexíveis de entrada.

### 6.1. Formato Array Direto
#### Corpo da Requisição
```json
["categoria", "preco_max", "disponivel"]
```

### 6.2. Formato Objeto com Chave
#### Corpo da Requisição
```json
{
  "parameter_ids": ["categoria", "preco_max", "disponivel"]
}
```

#### Exemplo de Resposta (Sucesso Total - 200)
```json
{
  "message": "3 parâmetros deletados permanentemente com sucesso",
  "status": "success",
  "deleted_parameters": ["categoria", "preco_max", "disponivel"],
  "total_deleted": 3,
  "action": "deletado permanentemente"
}
```

#### Exemplo de Resposta (Sucesso Parcial - 207)
```json
{
  "error": "Falha ao deletar alguns parâmetros: preco_max",
  "status": "partial_error",
  "deleted_parameters": ["categoria", "disponivel"],
  "failed_parameters": ["preco_max"],
  "total_deleted": 2,
  "total_failed": 1
}
```

---

## 📊 Códigos de Status HTTP

- **200 OK**: Operação realizada com sucesso
- **201 Created**: Recurso criado com sucesso
- **400 Bad Request**: Dados inválidos ou ausentes / Token JWT sem account_id
- **401 Unauthorized**: Token JWT ausente, inválido ou expirado
- **403 Forbidden**: Acesso negado - bot não pertence à sua conta
- **404 Not Found**: Bot, função ou recurso não encontrado
- **409 Conflict**: Recurso com o mesmo ID já existe
- **500 Internal Server Error**: Erro interno do servidor
- **503 Service Unavailable**: Banco de dados não está habilitado

## 🔐 Segurança e Validações

### Validações de Segurança
1. **Isolamento por Conta**: Usuários só podem acessar recursos de bots da própria conta
2. **Validação JWT**: Todos os endpoints requerem token válido
3. **Validação de UUID**: IDs são validados como UUID v4 quando aplicável
4. **Hierarquia de Permissões**: Parâmetros só podem ser acessados se a função pertencer ao bot da conta

### Validações de Dados
1. **Tamanhos de Campo**: Todos os campos têm limites de caracteres validados
2. **Tipos Controlados**: Apenas tipos pré-definidos são aceitos para parâmetros
3. **Formatos Específicos**: Validação de formatos como email, URI, date, date-time
4. **Regras de Exibição**: Apenas `first contact`, `every time` e `email not informed` são aceitos para `rule_display`
5. **Sanitização**: Dados são sanitizados antes de armazenar

## 🔄 Relacionamentos e Cascata

### Deleção em Cascata
- **Deletar Bot**: Não afeta prompts, funções ou parâmetros automaticamente
- **Deletar Função**: Remove automaticamente todos os parâmetros da função
- **Deletar Parâmetro**: Remove apenas o parâmetro específico

### Verificações de Integridade
- **Bot deve existir**: Antes de criar prompts ou funções
- **Função deve existir**: Antes de criar parâmetros
- **Propriedade da conta**: Todos os recursos devem pertencer à conta do usuário

## 📋 Exemplos Práticos por Tipo de rule_display

### Exemplo: first contact
```json
{
  "id": "welcome_new_user",
  "prompt": "🎉 Bem-vindo(a)! Este é seu primeiro contato conosco. Estamos aqui para ajudar!",
  "description": "Saudação para novos usuários",
  "rule_display": "first contact"
}
```

### Exemplo: every time
```json
{
  "id": "main_menu",
  "prompt": "📋 Menu Principal:\n1️⃣ Suporte\n2️⃣ Vendas\n3️⃣ FAQ\n\nDigite o número da opção desejada:",
  "description": "Menu sempre disponível",
  "rule_display": "every time"
}
```

### Exemplo: email not informed
```json
{
  "id": "collect_email",
  "prompt": "📧 Para melhor atendimento e acompanhamento, por favor informe seu email:",
  "description": "Coletar email quando não informado",
  "rule_display": "email not informed"
}
```

## 📝 Exemplos de Uso Completos

### Usando cURL

#### Criar um prompt:
```bash
curl -X POST https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000/prompts \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "prompt": "Olá! Como posso ajudá-lo hoje?",
    "description": "Mensagem de boas-vindas",
    "rule_display": "first contact"
  }'
```

#### Criar uma função:
```bash
curl -X POST https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000/functions \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "function_id": "buscar_produto",
    "description": "Buscar produtos no catálogo"
  }'
```

#### Criar um parâmetro único:
```bash
curl -X POST https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000/functions/buscar_produto/parameters \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "parameter_id": "categoria",
    "type": "string",
    "default_value": "eletronicos",
    "description": "Categoria do produto a ser buscado"
  }'
```

#### Criar múltiplos parâmetros (Batch):
```bash
curl -X POST https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000/functions/buscar_produto/parameters \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "parameter_id": "categoria",
      "type": "string",
      "permited_values": "[\"eletronicos\", \"roupas\", \"casa\"]",
      "default_value": "eletronicos",
      "description": "Categoria do produto a ser buscado"
    },
    {
      "parameter_id": "preco_max",
      "type": "number",
      "default_value": "1000",
      "description": "Preço máximo do produto"
    },
    {
      "parameter_id": "disponivel",
      "type": "boolean",
      "default_value": "true",
      "description": "Mostrar apenas produtos disponíveis"
    }
  ]'
```

#### Atualizar múltiplos parâmetros (Batch):
```bash
curl -X PUT https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000/functions/buscar_produto/parameters \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "parameter_id": "categoria",
      "type": "string",
      "permited_values": "[\"eletronicos\", \"roupas\", \"casa\", \"jardim\"]",
      "description": "Categoria atualizada com mais opções"
    },
    {
      "parameter_id": "preco_max",
      "default_value": "2000",
      "description": "Preço máximo aumentado"
    }
  ]'
```

#### Deletar múltiplos parâmetros (Batch) - Formato Array:
```bash
curl -X DELETE https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000/functions/buscar_produto/parameters \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '["categoria", "preco_max", "disponivel"]'
```

#### Deletar múltiplos parâmetros (Batch) - Formato Objeto:
```bash
curl -X DELETE https://atendimento.pluggerbi.com/bots/550e8400-e29b-41d4-a716-446655440000/functions/buscar_produto/parameters \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "parameter_ids": ["categoria", "preco_max", "disponivel"]
  }'
```

### Usando JavaScript (Frontend)

```javascript
// Classe para gerenciar extensões de bots
class BotExtensionsAPI {
  constructor(baseURL, jwtToken) {
    this.baseURL = baseURL;
    this.jwtToken = jwtToken;
  }

  async makeRequest(endpoint, method = 'GET', data = null) {
    const options = {
      method,
      headers: {
        'Authorization': `Bearer ${this.jwtToken}`,
        'Content-Type': 'application/json'
      }
    };

    if (data && (method === 'POST' || method === 'PUT')) {
      options.body = JSON.stringify(data);
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, options);
    return await response.json();
  }

  // Métodos para Prompts
  async getPrompts(botId) {
    return await this.makeRequest(`/bots/${botId}/prompts`);
  }

  async createPrompt(botId, promptData) {
    return await this.makeRequest(`/bots/${botId}/prompts`, 'POST', promptData);
  }

  async updatePrompt(botId, promptId, promptData) {
    return await this.makeRequest(`/bots/${botId}/prompts/${promptId}`, 'PUT', promptData);
  }

  async deletePrompt(botId, promptId) {
    return await this.makeRequest(`/bots/${botId}/prompts/${promptId}`, 'DELETE');
  }

  // Métodos para Functions
  async getFunctions(botId) {
    return await this.makeRequest(`/bots/${botId}/functions`);
  }

  async createFunction(botId, functionData) {
    return await this.makeRequest(`/bots/${botId}/functions`, 'POST', functionData);
  }

  async updateFunction(botId, functionId, functionData) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}`, 'PUT', functionData);
  }

  async deleteFunction(botId, functionId) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}`, 'DELETE');
  }

  // Métodos para Parameters
  async getParameters(botId, functionId) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}/parameters`);
  }

  async createParameter(botId, functionId, parameterData) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}/parameters`, 'POST', parameterData);
  }

  // Criar múltiplos parâmetros de uma vez (Batch)
  async createParametersBatch(botId, functionId, parametersArray) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}/parameters`, 'POST', parametersArray);
  }

  async updateParameter(botId, functionId, parameterId, parameterData) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}/parameters/${parameterId}`, 'PUT', parameterData);
  }

  // Atualizar múltiplos parâmetros de uma vez (Batch)
  async updateParametersBatch(botId, functionId, parametersArray) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}/parameters`, 'PUT', parametersArray);
  }

  async deleteParameter(botId, functionId, parameterId) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}/parameters/${parameterId}`, 'DELETE');
  }

  // Deletar múltiplos parâmetros de uma vez (Batch)
  async deleteParametersBatch(botId, functionId, parameterIds) {
    return await this.makeRequest(`/bots/${botId}/functions/${functionId}/parameters`, 'DELETE', parameterIds);
  }
}

// Exemplo de uso
const api = new BotExtensionsAPI('https://atendimento.pluggerbi.com', 'SEU_TOKEN_JWT');

// Criar um prompt
const promptData = {
  id: 'welcome_message',
  prompt: 'Olá! Como posso ajudá-lo hoje?',
  description: 'Mensagem de boas-vindas',
  rule_display: 'first contact'
};

api.createPrompt('550e8400-e29b-41d4-a716-446655440000', promptData)
  .then(result => console.log('Prompt criado:', result))
  .catch(error => console.error('Erro:', error));

// Criar função e múltiplos parâmetros
const functionData = {
  function_id: 'buscar_produto',
  description: 'Buscar produtos no catálogo'
};

const parameters = [
  {
    parameter_id: 'categoria',
    type: 'string',
    permited_values: '["eletronicos", "roupas", "casa"]',
    default_value: 'eletronicos',
    description: 'Categoria do produto a ser buscado'
  },
  {
    parameter_id: 'preco_max',
    type: 'number',
    default_value: '1000',
    description: 'Preço máximo do produto'
  }
];

// Criar função
api.createFunction('550e8400-e29b-41d4-a716-446655440000', functionData)
  .then(result => {
    console.log('Função criada:', result);
    // Criar múltiplos parâmetros de uma vez
    return api.createParametersBatch('550e8400-e29b-41d4-a716-446655440000', 'buscar_produto', parameters);
  })
  .then(result => console.log('Parâmetros criados:', result))
  .catch(error => console.error('Erro:', error));

// Atualizar múltiplos parâmetros
const updateParameters = [
  {
    parameter_id: 'categoria',
    permited_values: '["eletronicos", "roupas", "casa", "jardim", "esportes"]',
    description: 'Categoria atualizada com mais opções'
  },
  {
    parameter_id: 'preco_max',
    default_value: '2000',
    description: 'Preço máximo aumentado'
  }
];

api.updateParametersBatch('550e8400-e29b-41d4-a716-446655440000', 'buscar_produto', updateParameters)
  .then(result => console.log('Parâmetros atualizados:', result))
  .catch(error => console.error('Erro:', error));

// Deletar múltiplos parâmetros - Formato Array
const parametersToDelete = ['categoria', 'preco_max'];

api.deleteParametersBatch('550e8400-e29b-41d4-a716-446655440000', 'buscar_produto', parametersToDelete)
  .then(result => console.log('Parâmetros deletados:', result))
  .catch(error => console.error('Erro:', error));

// Deletar múltiplos parâmetros - Formato Objeto
const parametersToDeleteObj = {
  parameter_ids: ['categoria', 'preco_max', 'disponivel']
};

api.deleteParametersBatch('550e8400-e29b-41d4-a716-446655440000', 'buscar_produto', parametersToDeleteObj)
  .then(result => console.log('Parâmetros deletados:', result))
  .catch(error => console.error('Erro:', error));
```

## 🎯 Casos de Uso Práticos

### 1. Bot de E-commerce
```javascript
// Criando função de busca de produtos
const functionData = {
  function_id: 'buscar_produtos',
  description: 'Buscar produtos no catálogo baseado em critérios'
};

// Parâmetros da função - Batch Insert
const parameters = [
  {
    parameter_id: 'categoria',
    type: 'string',
    permited_values: '["eletronicos", "roupas", "casa"]',
    default_value: 'eletronicos',
    description: 'Categoria do produto a ser buscado'
  },
  {
    parameter_id: 'preco_max',
    type: 'number',
    default_value: '1000',
    description: 'Preço máximo do produto'
  },
  {
    parameter_id: 'disponivel',
    type: 'boolean',
    default_value: 'true',
    description: 'Mostrar apenas produtos disponíveis'
  }
];

// Criar múltiplos parâmetros de uma vez
const response = await fetch(`${baseURL}/bots/${botId}/functions/${functionId}/parameters`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(parameters) // Array de parâmetros
});

// Ou criar parâmetro único
const singleParameter = {
  parameter_id: 'ordenacao',
  type: 'string',
  permited_values: '["preco", "nome", "data"]',
  default_value: 'preco',
  description: 'Campo para ordenação dos resultados'
};

const singleResponse = await fetch(`${baseURL}/bots/${botId}/functions/${functionId}/parameters`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(singleParameter) // Objeto único
});
```

---

## 🚀 Resumo das Funcionalidades

### ✅ **Operações Batch de Parâmetros**

#### **Create (POST)**
- **Endpoint**: `POST /bots/{bot_id}/functions/{function_id}/parameters`
- **Aceita**: Objeto único ou array de parâmetros
- **Validação**: Todos validados antes de inserir qualquer um

#### **Update (PUT)**
- **Endpoint**: `PUT /bots/{bot_id}/functions/{function_id}/parameters` 
- **Aceita**: Array de objetos com `parameter_id` + campos a atualizar
- **Eficiência**: Atualiza múltiplos parâmetros em uma requisição

#### **Delete (DELETE)**
- **Endpoint**: `DELETE /bots/{bot_id}/functions/{function_id}/parameters`
- **Aceita**: Array direto ou objeto `{parameter_ids: [...]}`
- **Flexível**: Dois formatos de entrada aceitos

### ✅ **Estrutura Simplificada**
- **Functions**: `function_id` (nome interno) + `description`
- **Parameters**: `parameter_id` (nome) + `type` + `description`
- **Sem UUIDs desnecessários**: Chaves mais legíveis e intuitivas

### ✅ **Validação Robusta**
- **Campos obrigatórios**: Validação de presença e formato
- **Duplicatas**: Prevenção de parâmetros duplicados
- **Tipos**: Validação de tipos de dados suportados
- **Tamanhos**: Limites de caracteres respeitados

### 🎯 **Casos de Uso Ideais**
1. **Setup inicial**: Criar função com todos parâmetros de uma vez
2. **Configuração em lote**: Atualizar múltiplos parâmetros simultaneamente  
3. **Limpeza**: Deletar vários parâmetros obsoletos
4. **Migração**: Importar/exportar configurações completas
5. **Templates**: Aplicar configurações pré-definidas rapidamente
6. **Manutenção**: Operações em massa para otimização

### 2. Bot de Suporte com Movidesk
```javascript
// Prompts específicos para integração
const prompts = [
  {
    id: 'ticket_created',
    prompt: 'Seu chamado #{ticket_id} foi criado com sucesso. Acompanhe pelo portal.',
    description: 'Confirmação de criação de ticket',
    rule_display: 'every time'
  },
  {
    id: 'ticket_status',
    prompt: 'Status do seu chamado #{ticket_id}: {status}. Última atualização: {updated_at}',
    description: 'Informações de status do ticket',
    rule_display: 'every time'
  },
  {
    id: 'request_email',
    prompt: 'Para melhor atendimento, por favor informe seu email para acompanhamento do ticket.',
    description: 'Solicitar email quando não informado',
    rule_display: 'email not informed'
  }
];

// Função para criar ticket no Movidesk
const movideskFunction = {
  id: generateUUID(),
  name: 'criar_ticket_movidesk',
  goal: 'Criar novo ticket no sistema Movidesk'
};
```

---

# 🔗 Endpoints de Associação Prompt-Funções

Estes endpoints gerenciam a relação entre prompts e funções, permitindo que um prompt possa chamar uma ou mais funções específicas.

## Estrutura da Tabela

### bots_prompts_functions
```sql
CREATE TABLE `bots_prompts_functions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` varchar(36) DEFAULT NULL,
  `bot_id` varchar(45) DEFAULT NULL,
  `prompt_id` varchar(36) DEFAULT NULL,
  `function_id` varchar(150) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

Esta é uma tabela de relacionamento que suporta dois tipos de associações:

#### **Funções de Prompt** (`prompt_id` preenchido):
- Um prompt pode estar associado a várias funções
- Uma função pode estar associada a vários prompts
- Campos: `account_id`, `bot_id`, `prompt_id`, `function_id`

#### **Funções de Bot** (`prompt_id` NULL):
- Um bot pode ter funções que são executadas sempre
- Funções globais do bot, independente de prompts específicos
- Campos: `account_id`, `bot_id`, `function_id` (prompt_id = NULL)

## 1. Listar Funções de um Prompt
**GET** `/bots/{bot_id}/prompts/{prompt_id}/functions`

Lista todas as funções associadas a um prompt específico.

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "prompt_id": "123e4567-e89b-12d3-a456-426614174000",
  "functions": [
    {
      "id": 1,
      "account_id": "550e8400-e29b-41d4-a716-446655440001",
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "prompt_id": "123e4567-e89b-12d3-a456-426614174000",
      "function_id": "buscar_produto"
    },
    {
      "id": 2,
      "account_id": "550e8400-e29b-41d4-a716-446655440001",
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "prompt_id": "123e4567-e89b-12d3-a456-426614174000",
      "function_id": "calcular_preco"
    }
  ],
  "total": 2
}
```

#### Exemplo de Uso
```bash
curl -X GET "https://api.exemplo.com/bots/550e8400-e29b-41d4-a716-446655440000/prompts/123e4567-e89b-12d3-a456-426614174000/functions" \
  -H "Authorization: Bearer seu_jwt_token"
```

## 2. Associar Função a Prompt
**POST** `/bots/{bot_id}/prompts/{prompt_id}/functions`

Associa uma função existente a um prompt específico.

#### Corpo da Requisição
```json
{
  "function_id": "buscar_produto"
}
```

#### Campos Obrigatórios
- `function_id`: Nome interno da função (máximo 150 caracteres)

#### Validações
- A função deve existir no bot especificado
- A associação não pode duplicar uma existente
- O prompt deve existir no bot especificado
- O bot deve pertencer à conta do usuário

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Função associada ao prompt com sucesso",
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "prompt_id": "123e4567-e89b-12d3-a456-426614174000",
  "function_id": "buscar_produto"
}
```

#### Exemplo de Resposta (Conflito - 409)
```json
{
  "error": "Associação entre prompt e função já existe",
  "status": "error"
}
```

#### Exemplo de Uso
```bash
curl -X POST "https://api.exemplo.com/bots/550e8400-e29b-41d4-a716-446655440000/prompts/123e4567-e89b-12d3-a456-426614174000/functions" \
  -H "Authorization: Bearer seu_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{"function_id": "buscar_produto"}'
```

## 3. Remover Função de Prompt
**DELETE** `/bots/{bot_id}/prompts/{prompt_id}/functions/{function_id}`

Remove uma função específica de um prompt.

#### Parâmetros
- `bot_id` (UUID): ID do bot
- `prompt_id` (UUID): ID do prompt  
- `function_id` (string): ID da função (máximo 150 caracteres)

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Função removida do prompt com sucesso",
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "prompt_id": "123e4567-e89b-12d3-a456-426614174000",
  "function_id": "buscar_produto"
}
```

#### Exemplo de Resposta (Não Encontrado - 404)
```json
{
  "error": "Associação entre prompt e função não encontrada",
  "status": "error"
}
```

#### Exemplo de Uso
```bash
curl -X DELETE "https://api.exemplo.com/bots/550e8400-e29b-41d4-a716-446655440000/prompts/123e4567-e89b-12d3-a456-426614174000/functions/buscar_produto" \
  -H "Authorization: Bearer seu_jwt_token"
```

## Códigos de Status HTTP

### Sucesso
- **200** - OK: Operação realizada com sucesso
- **201** - Created: Associação criada com sucesso

### Erro do Cliente
- **400** - Bad Request: Dados inválidos ou UUIDs malformados
- **401** - Unauthorized: Token JWT inválido ou ausente
- **403** - Forbidden: Acesso negado ao bot
- **404** - Not Found: Bot, prompt, função ou associação não encontrados
- **409** - Conflict: Associação já existe

### Erro do Servidor
- **500** - Internal Server Error: Erro interno do servidor
- **503** - Service Unavailable: Banco de dados não disponível

## Validações e Regras de Negócio

### Segurança
- **Isolamento por Conta**: Todas as operações são filtradas por `account_id`
- **Validação de Propriedade**: Bot deve pertencer à conta do usuário
- **Existência de Recursos**: Bot, prompt e função devem existir antes da associação

### Validações de Dados
- **UUIDs**: `bot_id` e `prompt_id` devem ser UUIDs válidos
- **function_id**: Máximo 150 caracteres, deve existir no bot
- **Unicidade**: Não permite associações duplicadas (mesmo `account_id`, `prompt_id`, `function_id`)

### Casos de Uso Típicos

#### 1. Prompt com Múltiplas Funções
```javascript
// Um prompt de atendimento que pode executar várias ações
const promptId = "123e4567-e89b-12d3-a456-426614174000";

// Associar múltiplas funções
await associarFuncao(promptId, "buscar_produto");
await associarFuncao(promptId, "calcular_preco"); 
await associarFuncao(promptId, "verificar_estoque");
```

#### 2. Função Compartilhada
```javascript
// Uma função que pode ser chamada por vários prompts
const functionId = "buscar_produto";

await associarAPrompt("prompt_vendas", functionId);
await associarAPrompt("prompt_suporte", functionId);
await associarAPrompt("prompt_consulta", functionId);
```

#### 3. Gerenciamento Dinâmico
```javascript
// Listar funções atuais
const funcoes = await listarFuncoesDoPrompt(promptId);

// Remover função específica
await removerFuncaoDoPrompt(promptId, "funcao_antiga");

// Adicionar nova função
await associarFuncao(promptId, "funcao_nova");
```

## Exemplos de Integração

### Frontend (React/JavaScript)
```javascript
class PromptFunctionsManager {
  constructor(apiUrl, token) {
    this.apiUrl = apiUrl;
    this.token = token;
  }

  async listarFuncoes(botId, promptId) {
    const response = await fetch(
      `${this.apiUrl}/bots/${botId}/prompts/${promptId}/functions`,
      {
        headers: { Authorization: `Bearer ${this.token}` }
      }
    );
    return response.json();
  }

  async associarFuncao(botId, promptId, functionId) {
    const response = await fetch(
      `${this.apiUrl}/bots/${botId}/prompts/${promptId}/functions`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ function_id: functionId })
      }
    );
    return response.json();
  }

  async removerFuncao(botId, promptId, functionId) {
    const response = await fetch(
      `${this.apiUrl}/bots/${botId}/prompts/${promptId}/functions/${functionId}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${this.token}` }
      }
    );
    return response.json();
  }
}
```

### Backend (Python)
```python
import requests

class PromptFunctionsAPI:
    def __init__(self, api_url, token):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {token}"}

    def listar_funcoes(self, bot_id, prompt_id):
        url = f"{self.api_url}/bots/{bot_id}/prompts/{prompt_id}/functions"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def associar_funcao(self, bot_id, prompt_id, function_id):
        url = f"{self.api_url}/bots/{bot_id}/prompts/{prompt_id}/functions"
        data = {"function_id": function_id}
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def remover_funcao(self, bot_id, prompt_id, function_id):
        url = f"{self.api_url}/bots/{bot_id}/prompts/{prompt_id}/functions/{function_id}"
        response = requests.delete(url, headers=self.headers)
        return response.json()
```

---

# 🤖 Endpoints de Funções Associadas ao Bot

Estes endpoints gerenciam funções que são executadas sempre pelo bot, independentemente de prompts específicos. Essas funções ficam disponíveis globalmente no contexto do bot.

## 1. Listar Funções Associadas ao Bot
**GET** `/bots/{bot_id}/linked-functions`

Lista todas as funções associadas diretamente a um bot.

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "linked_functions": [
    {
      "id": 3,
      "account_id": "550e8400-e29b-41d4-a716-446655440001",
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "function_id": "buscar_produto"
    },
    {
      "id": 4,
      "account_id": "550e8400-e29b-41d4-a716-446655440001",
      "bot_id": "550e8400-e29b-41d4-a716-446655440000",
      "function_id": "verificar_estoque"
    }
  ],
  "total": 2
}
```

#### Exemplo de Uso
```bash
curl -X GET "https://api.exemplo.com/bots/550e8400-e29b-41d4-a716-446655440000/linked-functions" \
  -H "Authorization: Bearer seu_jwt_token"
```

## 2. Associar Função ao Bot
**POST** `/bots/{bot_id}/linked-functions`

Associa uma função existente diretamente ao bot (execução global).

#### Corpo da Requisição
```json
{
  "function_id": "buscar_produto"
}
```

#### Campos Obrigatórios
- `function_id`: Nome interno da função (máximo 150 caracteres)

#### Validações
- A função deve existir no bot especificado
- A associação não pode duplicar uma existente
- O bot deve pertencer à conta do usuário

#### Exemplo de Resposta (Sucesso - 201)
```json
{
  "message": "Função associada ao bot com sucesso",
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "function_id": "buscar_produto"
}
```

#### Exemplo de Resposta (Conflito - 409)
```json
{
  "error": "Associação entre bot e função já existe",
  "status": "error"
}
```

#### Exemplo de Uso
```bash
curl -X POST "https://api.exemplo.com/bots/550e8400-e29b-41d4-a716-446655440000/linked-functions" \
  -H "Authorization: Bearer seu_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{"function_id": "buscar_produto"}'
```

## 3. Remover Função do Bot
**DELETE** `/bots/{bot_id}/linked-functions/{function_id}`

Remove uma função específica das associações globais do bot.

#### Parâmetros
- `bot_id` (UUID): ID do bot
- `function_id` (string): ID da função (máximo 150 caracteres)

#### Exemplo de Resposta (Sucesso - 200)
```json
{
  "message": "Função removida do bot com sucesso",
  "status": "success",
  "bot_id": "550e8400-e29b-41d4-a716-446655440000",
  "function_id": "buscar_produto"
}
```

#### Exemplo de Resposta (Não Encontrado - 404)
```json
{
  "error": "Associação entre bot e função não encontrada",
  "status": "error"
}
```

#### Exemplo de Uso
```bash
curl -X DELETE "https://api.exemplo.com/bots/550e8400-e29b-41d4-a716-446655440000/linked-functions/buscar_produto" \
  -H "Authorization: Bearer seu_jwt_token"
```

## Diferenças entre Funções de Bot vs Funções de Prompt

### **Funções de Bot** (`/bots/{bot_id}/linked-functions`)
- **Escopo**: Global do bot
- **Execução**: Sempre disponíveis, independente do prompt
- **Uso**: Funções que devem estar sempre ativas (ex: buscar_produto, verificar_estoque)
- **Tabela**: `prompt_id` = NULL

### **Funções de Prompt** (`/bots/{bot_id}/prompts/{prompt_id}/functions`)
- **Escopo**: Específico do prompt
- **Execução**: Apenas quando o prompt específico é acionado
- **Uso**: Funções contextuais para prompts específicos
- **Tabela**: `prompt_id` preenchido

## Casos de Uso Típicos

### 1. Funções Globais do Bot
```javascript
// Funções que ficam sempre disponíveis
const botId = "550e8400-e29b-41d4-a716-446655440000";

await associarFuncaoAoBot(botId, "buscar_produto");
await associarFuncaoAoBot(botId, "verificar_estoque");
await associarFuncaoAoBot(botId, "calcular_preco");
```

### 2. Funções Específicas de Prompt
```javascript
// Funções que só aparecem em contextos específicos
const promptVendas = "123e4567-e89b-12d3-a456-426614174000";
const promptSuporte = "456e7890-e89b-12d3-a456-426614174001";

await associarFuncaoAoPrompt(botId, promptVendas, "processar_pagamento");
await associarFuncaoAoPrompt(botId, promptSuporte, "criar_ticket");
```

### 3. Combinação de Ambos
```javascript
// Bot com funções globais + específicas
const bot = {
  funcoes_globais: ["buscar_produto", "verificar_estoque"],
  prompts: {
    vendas: ["processar_pagamento", "aplicar_desconto"],
    suporte: ["criar_ticket", "escalar_atendimento"]
  }
};
```

## Exemplos de Integração

### Frontend (React/JavaScript)
```javascript
class BotFunctionsManager {
  constructor(apiUrl, token) {
    this.apiUrl = apiUrl;
    this.token = token;
  }

  // Funções de Bot (Globais)
  async listarFuncoesDoBot(botId) {
    const response = await fetch(
      `${this.apiUrl}/bots/${botId}/linked-functions`,
      {
        headers: { Authorization: `Bearer ${this.token}` }
      }
    );
    return response.json();
  }

  async associarFuncaoAoBot(botId, functionId) {
    const response = await fetch(
      `${this.apiUrl}/bots/${botId}/linked-functions`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ function_id: functionId })
      }
    );
    return response.json();
  }

  async removerFuncaoDoBot(botId, functionId) {
    const response = await fetch(
      `${this.apiUrl}/bots/${botId}/linked-functions/${functionId}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${this.token}` }
      }
    );
    return response.json();
  }

  // Funções de Prompt (Específicas)
  async listarFuncoesDoPrompt(botId, promptId) {
    const response = await fetch(
      `${this.apiUrl}/bots/${botId}/prompts/${promptId}/functions`,
      {
        headers: { Authorization: `Bearer ${this.token}` }
      }
    );
    return response.json();
  }
}
```

### Backend (Python)
```python
import requests

class BotFunctionsAPI:
    def __init__(self, api_url, token):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {token}"}

    # Funções de Bot (Globais)
    def listar_funcoes_bot(self, bot_id):
        url = f"{self.api_url}/bots/{bot_id}/linked-functions"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def associar_funcao_bot(self, bot_id, function_id):
        url = f"{self.api_url}/bots/{bot_id}/linked-functions"
        data = {"function_id": function_id}
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def remover_funcao_bot(self, bot_id, function_id):
        url = f"{self.api_url}/bots/{bot_id}/linked-functions/{function_id}"
        response = requests.delete(url, headers=self.headers)
        return response.json()

    # Funções de Prompt (Específicas)
    def listar_funcoes_prompt(self, bot_id, prompt_id):
        url = f"{self.api_url}/bots/{bot_id}/prompts/{prompt_id}/functions"
        response = requests.get(url, headers=self.headers)
        return response.json()
``` 