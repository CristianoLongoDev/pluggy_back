# Horizontal Pod Autoscaler (HPA) - Implementação

## 📋 **OVERVIEW**

O HPA foi implementado para permitir scaling automático baseado em CPU e memória, resolvendo problemas de capacidade e otimizando recursos.

## 🎯 **CONFIGURAÇÃO ATUAL**

### **Webhook Worker HPA**
- **Min Replicas**: 1
- **Max Replicas**: 3
- **CPU Target**: 70%
- **Memory Target**: 90% (ajustado)
- **Memory Request**: 40Mi (ajustado para uso real ~27Mi)

### **Message Worker HPA**
- **Min Replicas**: 1
- **Max Replicas**: 2
- **CPU Target**: 70%
- **Memory Target**: 90% (ajustado)
- **Memory Request**: 32Mi (ajustado para uso real ~27Mi)

### **Partitioned Workers HPA**
- **Min Replicas**: 1 (cada)
- **Max Replicas**: 2 (cada)
- **CPU Target**: 70%
- **Memory Target**: 80%

## 📊 **COMPORTAMENTO DE SCALING**

### **Scale-Up Policies:**
- **Stabilization Window**: 60 segundos
- **Max Scale**: 100% por minuto
- **Triggers**: CPU > 70% OU Memory > 80%

### **Scale-Down Policies:**
- **Stabilization Window**: 300 segundos (5 minutos)
- **Max Scale**: 50% por minuto
- **Cooldown**: Evita scaling agressivo

## 🔍 **COMANDOS DE MONITORAMENTO**

### **Status dos HPAs:**
```bash
kubectl get hpa -n whatsapp-webhook
```

### **Métricas dos Pods:**
```bash
kubectl top pods -n whatsapp-webhook
```

### **Eventos de Scaling:**
```bash
kubectl describe hpa webhook-worker-hpa -n whatsapp-webhook
```

### **Logs de Scaling:**
```bash
kubectl get events -n whatsapp-webhook --field-selector reason=SuccessfulRescale
```

## 📈 **RESULTADOS OBSERVADOS**

### **✅ SUCESSOS:**
- HPA detectou alta utilização de memória (>90%)
- Scale-up automático funcionando corretamente
- Scale-down automático após ajustes de resource requests
- Resource requests calibrados para uso real (~27Mi)
- Sistema estável em 1 replica sem uso

### **✅ CORREÇÕES IMPLEMENTADAS:**
- **Memory targets**: 80% → 90% (mais tolerante)
- **Webhook memory request**: 24Mi → 40Mi (cobriu uso real)
- **Message memory request**: 24Mi → 32Mi (cobriu uso real)
- **Resultado**: HPA agora funciona conforme esperado

### **⚠️ LIMITAÇÕES ATUAIS:**
- Cluster com recursos limitados para scale-up massivo
- Alguns pods podem ficar Pending em alta carga

## 🎯 **PRÓXIMAS OTIMIZAÇÕES**

### **1. Aumentar Recursos do Cluster:**
- Adicionar mais nós worker
- Aumentar CPU/Memory por nó

### **2. Ajustar Limites:**
- Revisar resource requests/limits
- Otimizar memory target (talvez 85%)

### **3. Métricas Customizadas:**
- HPA baseado em RabbitMQ queue size
- HPA baseado em latência de resposta

## 🔧 **TROUBLESHOOTING**

### **Pod Pending:**
```bash
kubectl describe pod <pod-name> -n whatsapp-webhook
```

### **HPA Não Scaling:**
```bash
kubectl describe hpa <hpa-name> -n whatsapp-webhook
kubectl get events -n whatsapp-webhook
```

### **Metrics Server Issues:**
```bash
kubectl get deployment metrics-server -n kube-system
kubectl logs -n kube-system deployment/metrics-server
```

## 📊 **ARQUIVOS RELACIONADOS**

- `k8s/hpa-webhook-worker.yaml`
- `k8s/hpa-message-worker.yaml`
- `k8s/hpa-partitioned-workers.yaml`
- `scripts/monitor-hpa.sh`
