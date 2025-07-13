#!/usr/bin/env python3
"""
Script de renovação automática de tokens WhatsApp
Executa verificação periódica e renova tokens quando necessário
"""

import os
import sys
import time
import logging
from datetime import datetime

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from whatsapp_service import whatsapp_service
from database import db_manager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/token_renewal.log')
    ]
)

logger = logging.getLogger(__name__)

class TokenAutoRenewal:
    def __init__(self):
        self.check_interval = 3600  # Verificar a cada 1 hora
        self.renewal_threshold = 86400  # Renovar se falta menos de 24 horas
        
    def check_and_renew_token(self):
        """Verifica e renova token se necessário"""
        logger.info("🔄 Iniciando verificação automática de token...")
        
        try:
            # Verificar status do token
            token_status = whatsapp_service.get_token_status()
            
            logger.info(f"Status do token: {token_status.get('status')}")
            logger.info(f"Mensagem: {token_status.get('message')}")
            
            if token_status.get('status') == 'valid':
                expires_in_hours = token_status.get('expires_in_hours', 0)
                
                if expires_in_hours < 24:  # Menos de 24 horas
                    logger.warning(f"⚠️ Token expira em {expires_in_hours:.1f} horas - renovando...")
                    
                    # Tentar renovar
                    success = whatsapp_service.refresh_token_if_needed()
                    
                    if success:
                        logger.info("✅ Token renovado com sucesso!")
                        
                        # Verificar novo status
                        new_status = whatsapp_service.get_token_status()
                        new_expires_in = new_status.get('expires_in_hours', 0)
                        logger.info(f"Novo token válido por {new_expires_in:.1f} horas")
                        
                        return True
                    else:
                        logger.error("❌ Falha ao renovar token automaticamente")
                        return False
                else:
                    logger.info(f"✅ Token válido por mais {expires_in_hours:.1f} horas")
                    return True
                    
            elif token_status.get('status') == 'expired':
                logger.error("❌ Token expirado - autorização OAuth necessária")
                return False
                
            elif token_status.get('status') == 'not_found':
                logger.error("❌ Token não encontrado - autorização OAuth necessária")
                return False
                
            else:
                logger.error(f"❌ Status desconhecido: {token_status.get('status')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro na verificação automática: {e}")
            return False
    
    def run_once(self):
        """Executa verificação uma vez"""
        logger.info("=" * 50)
        logger.info("🚀 VERIFICAÇÃO AUTOMÁTICA DE TOKEN")
        logger.info("=" * 50)
        
        result = self.check_and_renew_token()
        
        if result:
            logger.info("✅ Verificação concluída com sucesso")
            return True
        else:
            logger.error("❌ Verificação falhou")
            return False
    
    def run_continuous(self):
        """Executa verificação contínua"""
        logger.info("🔄 Iniciando verificação contínua de tokens...")
        logger.info(f"Intervalo: {self.check_interval} segundos ({self.check_interval/3600:.1f} horas)")
        
        while True:
            try:
                self.run_once()
                
                logger.info(f"😴 Aguardando {self.check_interval/3600:.1f} horas para próxima verificação...")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro inesperado: {e}")
                logger.info("⏰ Aguardando 5 minutos antes de tentar novamente...")
                time.sleep(300)  # 5 minutos
    
    def get_renewal_status(self):
        """Retorna status para monitoramento"""
        try:
            token_status = whatsapp_service.get_token_status()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "token_status": token_status,
                "auto_renewal_active": True,
                "next_check": datetime.now().timestamp() + self.check_interval
            }
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "auto_renewal_active": False
            }

def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Renovação automática de tokens WhatsApp')
    parser.add_argument('--once', action='store_true', help='Executar verificação uma vez')
    parser.add_argument('--continuous', action='store_true', help='Executar verificação contínua')
    parser.add_argument('--status', action='store_true', help='Mostrar status atual')
    
    args = parser.parse_args()
    
    renewal = TokenAutoRenewal()
    
    if args.once:
        success = renewal.run_once()
        sys.exit(0 if success else 1)
    
    elif args.continuous:
        renewal.run_continuous()
    
    elif args.status:
        status = renewal.get_renewal_status()
        print(f"Status: {status}")
    
    else:
        print("Uso: python token_auto_renewal.py [--once|--continuous|--status]")
        print("  --once      : Executar verificação uma vez")
        print("  --continuous: Executar verificação contínua")
        print("  --status    : Mostrar status atual")

if __name__ == "__main__":
    main() 