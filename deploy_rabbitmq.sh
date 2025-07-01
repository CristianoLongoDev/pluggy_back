#!/bin/bash

echo "🐰 Fazendo deploy do RabbitMQ e Workers..."
echo "=================================================="

# Função para verificar se um pod está pronto
wait_for_pod() {
    local app_label=$1
    local namespace=$2
    local timeout=${3:-300}
    
    echo "⏳ Aguardando pod $app_label ficar pronto..."
    kubectl wait --for=condition=Ready pod -l app=$app_label -n $namespace --timeout=${timeout}s
    
    if [ $? -eq 0 ]; then
        echo "✅ Pod $app_label está pronto!"
        return 0
    else
        echo "❌ Timeout aguardando pod $app_label"
        return 1
    fi
}

# 1. Deploy do RabbitMQ
echo ""
echo "📦 1. Fazendo deploy do RabbitMQ..."
kubectl apply -f k8s/rabbitmq-deployment.yaml

if [ $? -eq 0 ]; then
    echo "✅ RabbitMQ deployment aplicado com sucesso"
    
    # Aguardar RabbitMQ ficar pronto
    wait_for_pod "rabbitmq" "whatsapp-webhook" 300
    
    if [ $? -eq 0 ]; then
        echo "✅ RabbitMQ está funcionando!"
    else
        echo "❌ RabbitMQ não ficou pronto a tempo"
        exit 1
    fi
else
    echo "❌ Erro ao aplicar RabbitMQ deployment"
    exit 1
fi

# 2. Atualizar ConfigMap
echo ""
echo "📝 2. Atualizando ConfigMap com código atualizado..."
kubectl apply -f k8s/configmap.yaml

if [ $? -eq 0 ]; then
    echo "✅ ConfigMap atualizado com sucesso"
else
    echo "❌ Erro ao atualizar ConfigMap"
    exit 1
fi

# 3. Reiniciar aplicação principal
echo ""
echo "🔄 3. Reiniciando aplicação principal..."
kubectl rollout restart deployment/whatsapp-webhook -n whatsapp-webhook

if [ $? -eq 0 ]; then
    echo "✅ Aplicação principal reiniciada"
    
    # Aguardar aplicação ficar pronta
    wait_for_pod "whatsapp-webhook" "whatsapp-webhook" 180
    
    if [ $? -eq 0 ]; then
        echo "✅ Aplicação principal está funcionando!"
    else
        echo "⚠️ Aplicação principal pode ainda estar iniciando"
    fi
else
    echo "❌ Erro ao reiniciar aplicação principal"
fi

# 4. Deploy dos Workers
echo ""
echo "👷 4. Fazendo deploy dos Workers..."
kubectl apply -f k8s/webhook-worker-deployment.yaml

if [ $? -eq 0 ]; then
    echo "✅ Workers deployment aplicado com sucesso"
    
    # Aguardar workers ficarem prontos
    echo "⏳ Aguardando workers ficarem prontos..."
    sleep 30
    
    webhook_worker_status=$(kubectl get pods -n whatsapp-webhook -l app=webhook-worker --no-headers | wc -l)
    message_worker_status=$(kubectl get pods -n whatsapp-webhook -l app=message-worker --no-headers | wc -l)
    
    echo "📊 Workers status:"
    echo "  - Webhook workers: $webhook_worker_status pods"
    echo "  - Message workers: $message_worker_status pods"
    
else
    echo "❌ Erro ao aplicar Workers deployment"
    exit 1
fi

# 5. Verificar status geral
echo ""
echo "🔍 5. Verificando status geral..."
echo ""

echo "📊 STATUS DOS PODS:"
kubectl get pods -n whatsapp-webhook -o wide

echo ""
echo "🌐 STATUS DOS SERVICES:"
kubectl get services -n whatsapp-webhook

echo ""
echo "📋 STATUS DOS DEPLOYMENTS:"
kubectl get deployments -n whatsapp-webhook

# 6. Verificar logs do RabbitMQ
echo ""
echo "📋 6. Últimos logs do RabbitMQ:"
kubectl logs -n whatsapp-webhook -l app=rabbitmq --tail=5

# 7. Informações úteis
echo ""
echo "=================================================="
echo "🎉 DEPLOY CONCLUÍDO!"
echo "=================================================="
echo ""
echo "📋 INFORMAÇÕES ÚTEIS:"
echo ""
echo "🔗 Para acessar a interface do RabbitMQ:"
echo "   kubectl port-forward -n whatsapp-webhook svc/rabbitmq-management 15672:15672"
echo "   Depois acesse: http://localhost:15672"
echo "   Usuário: admin"
echo "   Senha: rabbitmq123"
echo ""
echo "📊 Para verificar status da aplicação:"
echo "   kubectl get pods -n whatsapp-webhook"
echo ""
echo "📋 Para ver logs:"
echo "   kubectl logs -n whatsapp-webhook -l app=whatsapp-webhook"
echo "   kubectl logs -n whatsapp-webhook -l app=webhook-worker"
echo "   kubectl logs -n whatsapp-webhook -l app=message-worker"
echo "   kubectl logs -n whatsapp-webhook -l app=rabbitmq"
echo ""
echo "🧪 Para testar o webhook:"
echo "   curl -X POST https://atendimento.pluggerbi.com/webhook \\"
echo "        -H 'Content-Type: application/json' \\"
echo "        -d '{\"test\": \"message\"}'"
echo ""
echo "🔍 Para verificar filas RabbitMQ via API:"
echo "   curl https://atendimento.pluggerbi.com/rabbitmq/status"
echo ""
echo "==================================================" 