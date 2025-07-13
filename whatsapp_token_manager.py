import json
import logging
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode
from database import db_manager

logger = logging.getLogger(__name__)

class WhatsAppTokenManager:
    def __init__(self):
        self.app_id = "983764203018472"
        self.app_secret = "ae9b212c99dcb6a255e6dad2acc6b484"
        
    def get_long_lived_token(self, short_lived_token):
        """Converte token de curta duração para longa duração (60 dias)"""
        try:
            params = {
                'grant_type': 'fb_exchange_token',
                'client_id': self.app_id,
                'client_secret': self.app_secret,
                'fb_exchange_token': short_lived_token
            }
            
            exchange_url = f"https://graph.facebook.com/v18.0/oauth/access_token?{urlencode(params)}"
            
            response = requests.get(exchange_url, timeout=30)
            
            if response.status_code == 200:
                long_lived_data = response.json()
                
                # Adicionar timestamp de criação e expiração (60 dias)
                now = datetime.now()
                expires_in = long_lived_data.get('expires_in', 5184000)  # 60 dias em segundos
                
                enhanced_long_lived_data = {
                    'access_token': long_lived_data.get('access_token'),
                    'expires_in': expires_in,
                    'created_at': now.isoformat(),
                    'expires_at': (now + timedelta(seconds=expires_in)).isoformat(),
                    'token_type': long_lived_data.get('token_type', 'Bearer'),
                    'is_long_lived': True,
                    'raw_response': long_lived_data
                }
                
                # Salvar token de longa duração no banco
                db_manager.set_config(
                    'whatsapp_token',
                    enhanced_long_lived_data,
                    'Token de longa duração WhatsApp (60 dias)'
                )
                
                logger.info(f"Token de longa duração salvo (expira em {expires_in/86400:.1f} dias)")
                return enhanced_long_lived_data
                
            else:
                logger.warning(f"Não foi possível obter token de longa duração: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao obter token de longa duração: {e}")
            return None
    
    def is_token_expired(self, token_data):
        """Verifica se o token está expirado ou próximo do vencimento"""
        if not token_data or 'expires_at' not in token_data:
            return True
            
        try:
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            now = datetime.now()
            
            # Considerar expirado se falta menos de 1 hora para vencer
            time_until_expiry = expires_at - now
            
            if time_until_expiry.total_seconds() < 3600:  # 1 hora
                logger.warning(f"Token expira em {time_until_expiry.total_seconds()/60:.1f} minutos")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Erro ao verificar expiração do token: {e}")
            return True
    
    def refresh_token_if_needed(self):
        """Renova token automaticamente se necessário"""
        try:
            token_data = db_manager.get_config('whatsapp_token')
            
            if not token_data:
                logger.warning("Nenhum token encontrado - autorização OAuth necessária")
                return False
                
            if not self.is_token_expired(token_data):
                logger.debug("Token ainda válido, não precisa renovar")
                return True
                
            logger.info("Token expirando, tentando renovar...")
            
            # Se é token de longa duração, tentar obter um novo
            if token_data.get('is_long_lived'):
                logger.info("Renovando token de longa duração...")
                new_token = self.get_long_lived_token(token_data['access_token'])
                
                if new_token:
                    logger.info("Token renovado com sucesso!")
                    return True
                else:
                    logger.error("Falha ao renovar token de longa duração")
                    return False
            else:
                logger.warning("Token de curta duração expirado - nova autorização OAuth necessária")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao renovar token: {e}")
            return False
    
    def get_token_status(self):
        """Retorna status detalhado do token"""
        try:
            token_data = db_manager.get_config('whatsapp_token')
            
            if not token_data:
                return {
                    "status": "not_found",
                    "message": "Token não encontrado - autorização OAuth necessária"
                }
            
            if not self.is_token_expired(token_data):
                expires_at = datetime.fromisoformat(token_data['expires_at'])
                time_until_expiry = expires_at - datetime.now()
                
                return {
                    "status": "valid",
                    "expires_at": token_data['expires_at'],
                    "expires_in_hours": time_until_expiry.total_seconds() / 3600,
                    "is_long_lived": token_data.get('is_long_lived', False),
                    "message": f"Token válido por mais {time_until_expiry.total_seconds()/3600:.1f} horas"
                }
            else:
                return {
                    "status": "expired",
                    "expires_at": token_data.get('expires_at'),
                    "message": "Token expirado - renovação necessária"
                }
                
        except Exception as e:
            logger.error(f"Erro ao verificar status do token: {e}")
            return {
                "status": "error",
                "message": f"Erro ao verificar token: {str(e)}"
            }
    
    def setup_auto_renewal_task(self):
        """Configura tarefa automática de renovação (executar periodicamente)"""
        try:
            # Verificar token a cada execução
            result = self.refresh_token_if_needed()
            
            if result:
                logger.info("✅ Verificação automática de token concluída")
                return True
            else:
                logger.error("❌ Falha na verificação automática de token")
                return False
                
        except Exception as e:
            logger.error(f"Erro na tarefa automática de renovação: {e}")
            return False

# Instância global do gerenciador de tokens
token_manager = WhatsAppTokenManager() 