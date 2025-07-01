#!/bin/bash

# Script para atualizar o ConfigMap com os arquivos mais recentes

echo "🔄 Atualizando ConfigMap..."

# Criar ConfigMap temporário
cat > k8s/configmap_temp.yaml << 'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: whatsapp-webhook-config
  namespace: whatsapp-webhook
data:
EOF

# Adicionar app.py
echo "" >> k8s/configmap_temp.yaml
echo "  app.py: |" >> k8s/configmap_temp.yaml
sed 's/^/    /' app.py >> k8s/configmap_temp.yaml

# Adicionar database.py
echo "" >> k8s/configmap_temp.yaml
echo "  database.py: |" >> k8s/configmap_temp.yaml
sed 's/^/    /' database.py >> k8s/configmap_temp.yaml

# Adicionar config.py
echo "" >> k8s/configmap_temp.yaml
echo "  config.py: |" >> k8s/configmap_temp.yaml
sed 's/^/    /' config.py >> k8s/configmap_temp.yaml

# Adicionar rabbitmq_manager.py
echo "" >> k8s/configmap_temp.yaml
echo "  rabbitmq_manager.py: |" >> k8s/configmap_temp.yaml
sed 's/^/    /' rabbitmq_manager.py >> k8s/configmap_temp.yaml

# Adicionar webhook_worker.py
echo "" >> k8s/configmap_temp.yaml
echo "  webhook_worker.py: |" >> k8s/configmap_temp.yaml
sed 's/^/    /' webhook_worker.py >> k8s/configmap_temp.yaml

# Adicionar requirements.txt
echo "" >> k8s/configmap_temp.yaml
echo "  requirements.txt: |" >> k8s/configmap_temp.yaml
sed 's/^/    /' requirements.txt >> k8s/configmap_temp.yaml

# Adicionar frontend
echo "" >> k8s/configmap_temp.yaml
echo "  index.html: |" >> k8s/configmap_temp.yaml
sed 's/^/    /' frontend/index.html >> k8s/configmap_temp.yaml

# Substituir arquivo original
mv k8s/configmap_temp.yaml k8s/configmap.yaml

echo "✅ ConfigMap atualizado com sucesso!"
echo "📋 Para aplicar as mudanças:"
echo "   kubectl apply -f k8s/configmap.yaml"
echo "   kubectl rollout restart deployment/whatsapp-webhook -n whatsapp-webhook" 