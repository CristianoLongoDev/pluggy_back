# Guia de Migração: JWT Secret → JWT Signing Keys

Este guia explica como migrar da API legacy do Supabase (JWT Secret) para a nova API com JWT Signing Keys.

## 📋 O que mudou?

### ❌ **ANTES (Legacy JWT Secret):**
```bash
# Configuração antiga
SUPABASE_JWT_SECRET=seu_jwt_secret_aqui
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua_anon_key_aqui

# Validação HMAC (HS256)
jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=['HS256'])
```

### ✅ **AGORA (JWT Signing Keys):**
```bash
# Configuração nova (mais simples!)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua_anon_key_aqui
# Não precisa mais do JWT_SECRET!

# Validação RSA/ECDSA automática
# Busca chaves públicas do endpoint /auth/v1/jwks
```

## 🔧 Passos para migração

### 1. **Atualizar o código** ✅ **(JÁ FEITO)**
- [x] Nova função `validate_jwt_token()` com PyJWKClient
- [x] Cache inteligente das chaves públicas (1 hora)
- [x] Suporte a RS256 e ES256
- [x] Validação de `iss`, `aud`, `kid`

### 2. **Atualizar configuração do Kubernetes**

#### **Remover variável antiga:**
```yaml
# k8s/deployment.yaml - REMOVIDO
- name: SUPABASE_JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: whatsapp-webhook-secret
      key: SUPABASE_JWT_SECRET
```

#### **Atualizar secret:**
```yaml
# k8s/secret.yaml - ATUALIZADO
# Remover linha do SUPABASE_JWT_SECRET
# Manter apenas:
SUPABASE_URL: aHR0cHM6Ly9zZXUtcHJvamV0by5zdXBhYmFzZS5jbw==
SUPABASE_ANON_KEY: c3VhX3N1cGFiYXNlX2Fub25fa2V5X2FxdWk=
```

### 3. **Configurar valores reais**

```bash
# 1. Obter valores do Supabase
# - URL: https://app.supabase.com > Project Settings > General
# - ANON_KEY: https://app.supabase.com > Project Settings > API

# 2. Codificar em base64
echo -n "https://seuprojetoverdadeiro.supabase.co" | base64
echo -n "sua_anon_key_verdadeira_aqui" | base64

# 3. Atualizar k8s/secret.yaml com os valores reais
```

### 4. **Deploy das mudanças**

```bash
# Deploy completo
./deploy.sh

# Ou apenas atualizar o secret
kubectl apply -f k8s/secret.yaml
kubectl rollout restart deployment/whatsapp-webhook -n whatsapp-webhook
```

## 🧪 Testando a migração

### 1. **Verificar configuração (público):**
```bash
curl https://atendimento.pluggerbi.com/auth/jwt/status
```

**Resposta esperada:**
```json
{
  "status": "success",
  "jwt_configuration": {
    "supabase_url_configured": true,
    "jwks_url": "https://seuprojetoverdadeiro.supabase.co/auth/v1/jwks",
    "jwks_client_initialized": true,
    "jwks_endpoint_accessible": true,
    "jwks_keys_count": 2
  }
}
```

### 2. **Testar autenticação (requer token):**
```bash
curl -X POST https://atendimento.pluggerbi.com/auth/jwt/test \
  -H "Authorization: Bearer SEU_TOKEN_JWT_DO_SUPABASE"
```

### 3. **Testar endpoint de conta:**
```bash
curl -X GET https://atendimento.pluggerbi.com/accounts/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer SEU_TOKEN_JWT_DO_SUPABASE"
```

## 🚨 Troubleshooting

### **Erro: "SUPABASE_JWKS_URL não configurado"**
- Verifique se `SUPABASE_URL` está configurado corretamente
- URL deve ser sem trailing slash: `https://projeto.supabase.co`

### **Erro: "Token JWT sem 'kid' no header"**
- Token pode ser do formato antigo
- Gere um novo token no Supabase

### **Erro: "jwks_endpoint_accessible": false**
- Verifique conectividade com `https://projeto.supabase.co/auth/v1/jwks`
- Pode ser problema de rede/firewall

### **Erro: "Erro ao obter chave pública para kid"**
- Token pode ter sido gerado com chave antiga
- Aguarde alguns minutos para cache expirar ou gere novo token

## ✅ Vantagens da nova abordagem

1. **🔐 Mais segura**: Chaves públicas vs secrets compartilhados
2. **🔄 Rotação automática**: Supabase gerencia as chaves
3. **📦 Menos configuração**: Não precisa do JWT secret
4. **⚡ Performance**: Cache inteligente das chaves
5. **🎯 Padrão da indústria**: Segue RFC 7517 (JWKS)

## 📝 Logs úteis

```bash
# Ver logs da aplicação
kubectl logs -f deployment/whatsapp-webhook -n whatsapp-webhook

# Buscar por logs JWT específicos
kubectl logs deployment/whatsapp-webhook -n whatsapp-webhook | grep -i jwt
```

## 🔗 Documentação oficial

- [Supabase JWT Signing Keys](https://supabase.com/docs/guides/auth/server-side/nextjs#jwt-signing-keys)
- [RFC 7517 - JSON Web Key (JWK)](https://tools.ietf.org/html/rfc7517)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/) 