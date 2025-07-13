#!/bin/bash
# Script de configuração para automação de tokens WhatsApp
# Configura cron jobs e serviços systemd para verificação automática

echo "🔧 Configurando automação de tokens WhatsApp..."

# Diretório do projeto
PROJECT_DIR="/home/repo/whatsapp"
SCRIPT_PATH="$PROJECT_DIR/token_auto_renewal.py"
LOG_FILE="/tmp/token_renewal.log"

# Verificar se o script existe
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Script não encontrado: $SCRIPT_PATH"
    exit 1
fi

# Tornar o script executável
chmod +x "$SCRIPT_PATH"

echo "📋 Opções de automação:"
echo "1. Cron Job (verificação a cada hora)"
echo "2. Serviço systemd (execução contínua)"
echo "3. Script manual (executar uma vez)"
echo "4. Verificar status atual"
echo "5. Ver logs"

read -p "Escolha uma opção (1-5): " choice

case $choice in
    1)
        echo "⏰ Configurando Cron Job..."
        
        # Criar entrada no crontab
        CRON_ENTRY="0 * * * * cd $PROJECT_DIR && python3 token_auto_renewal.py --once >> $LOG_FILE 2>&1"
        
        # Adicionar ao crontab se não existir
        if ! crontab -l 2>/dev/null | grep -q "token_auto_renewal.py"; then
            (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
            echo "✅ Cron job adicionado com sucesso!"
            echo "📄 Entrada: $CRON_ENTRY"
        else
            echo "⚠️ Cron job já existe"
        fi
        
        echo "📊 Para ver os logs: tail -f $LOG_FILE"
        ;;
        
    2)
        echo "🔄 Configurando serviço systemd..."
        
        # Criar arquivo de serviço
        SERVICE_FILE="/etc/systemd/system/whatsapp-token-renewal.service"
        
        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=WhatsApp Token Auto Renewal Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_PATH --continuous
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

        # Recarregar systemd e iniciar serviço
        sudo systemctl daemon-reload
        sudo systemctl enable whatsapp-token-renewal
        sudo systemctl start whatsapp-token-renewal
        
        echo "✅ Serviço systemd configurado e iniciado!"
        echo "📊 Para ver status: sudo systemctl status whatsapp-token-renewal"
        echo "📄 Para ver logs: sudo journalctl -u whatsapp-token-renewal -f"
        ;;
        
    3)
        echo "🔄 Executando verificação manual..."
        cd "$PROJECT_DIR"
        python3 token_auto_renewal.py --once
        ;;
        
    4)
        echo "📊 Status atual do token:"
        cd "$PROJECT_DIR"
        python3 token_auto_renewal.py --status
        ;;
        
    5)
        echo "📄 Logs de renovação:"
        if [ -f "$LOG_FILE" ]; then
            tail -50 "$LOG_FILE"
        else
            echo "⚠️ Arquivo de log não encontrado: $LOG_FILE"
        fi
        ;;
        
    *)
        echo "❌ Opção inválida"
        exit 1
        ;;
esac

echo ""
echo "🎯 Comandos úteis:"
echo "• Verificar token: curl http://localhost:8080/bot/token/status"
echo "• Forçar renovação: curl -X POST http://localhost:8080/bot/token/refresh"
echo "• Ver logs: tail -f $LOG_FILE"
echo "• Parar cron: crontab -e (remover linha)"
echo "• Parar serviço: sudo systemctl stop whatsapp-token-renewal"

echo ""
echo "✅ Configuração concluída!" 