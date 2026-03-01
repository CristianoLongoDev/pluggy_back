#!/bin/bash

# Script para monitorar HPA em tempo real
# Uso: ./scripts/monitor-hpa.sh

NAMESPACE="whatsapp-webhook"

echo "🚀 MONITORAMENTO HPA - WHATSAPP WEBHOOK"
echo "========================================="
echo ""

# Função para mostrar status completo
show_status() {
    echo "📊 STATUS DOS HPAs:"
    kubectl get hpa -n $NAMESPACE
    echo ""
    
    echo "📈 MÉTRICAS DOS PODS:"
    kubectl top pods -n $NAMESPACE
    echo ""
    
    echo "🔢 CONTAGEM DE PODS:"
    echo "Total pods: $(kubectl get pods -n $NAMESPACE --no-headers | wc -l)"
    echo "Running: $(kubectl get pods -n $NAMESPACE --no-headers | grep Running | wc -l)"
    echo "Pending: $(kubectl get pods -n $NAMESPACE --no-headers | grep Pending | wc -l)"
    echo ""
    
    echo "⚠️ PODS COM PROBLEMAS:"
    kubectl get pods -n $NAMESPACE --no-headers | grep -v Running || echo "✅ Todos os pods funcionando!"
    echo ""
    
    echo "🎯 TARGETS vs ATUAL:"
    kubectl get hpa -n $NAMESPACE -o custom-columns="NAME:.metadata.name,TARGETS:.status.currentMetrics[*].resource.current.averageUtilization,CPU-TARGET:.spec.metrics[0].resource.target.averageUtilization,MEM-TARGET:.spec.metrics[1].resource.target.averageUtilization"
    echo ""
}

# Função para modo contínuo
monitor_continuous() {
    echo "🔄 MODO CONTÍNUO (Ctrl+C para parar)"
    echo "====================================="
    
    while true; do
        clear
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Monitoramento HPA"
        echo "=================================================="
        show_status
        sleep 30
    done
}

# Função para mostrar eventos recentes
show_events() {
    echo "📋 EVENTOS RECENTES DE SCALING:"
    kubectl get events -n $NAMESPACE --field-selector reason=SuccessfulRescale --sort-by='.lastTimestamp' | tail -10
    echo ""
    
    echo "📋 EVENTOS DE FAILED SCHEDULING:"
    kubectl get events -n $NAMESPACE --field-selector reason=FailedScheduling --sort-by='.lastTimestamp' | tail -5
    echo ""
}

# Função para análise detalhada
detailed_analysis() {
    echo "🔍 ANÁLISE DETALHADA:"
    echo "===================="
    
    for hpa in $(kubectl get hpa -n $NAMESPACE -o name); do
        echo ""
        echo "📊 $hpa:"
        kubectl describe $hpa -n $NAMESPACE | grep -A 10 -B 5 "Metrics\|Conditions\|Events"
        echo "---"
    done
}

# Menu principal
case "${1:-status}" in
    "status"|"s")
        show_status
        ;;
    "continuous"|"c")
        monitor_continuous
        ;;
    "events"|"e")
        show_events
        ;;
    "detailed"|"d")
        detailed_analysis
        ;;
    "help"|"h")
        echo "🚀 MONITOR HPA - OPÇÕES:"
        echo ""
        echo "  status (s)     - Mostra status atual (padrão)"
        echo "  continuous (c) - Monitoramento contínuo"
        echo "  events (e)     - Eventos recentes"
        echo "  detailed (d)   - Análise detalhada"
        echo "  help (h)       - Esta ajuda"
        echo ""
        echo "Exemplos:"
        echo "  ./scripts/monitor-hpa.sh"
        echo "  ./scripts/monitor-hpa.sh continuous"
        echo "  ./scripts/monitor-hpa.sh events"
        ;;
    *)
        echo "❌ Opção inválida. Use: ./scripts/monitor-hpa.sh help"
        exit 1
        ;;
esac
