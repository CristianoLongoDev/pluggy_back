import requests
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode
from database import db_manager
from whatsapp_token_manager import token_manager

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.app_id = "983764203018472"
        self.app_secret = "ae9b212c99dcb6a255e6dad2acc6b484"
        self.phone_number_id = "421769451025047"
        self.api_version = "v17.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.messages_url = f"{self.base_url}/{self.phone_number_id}/messages"
        
    def get_oauth_url(self, redirect_uri):
        """Gera URL para autorização OAuth do WhatsApp"""
        params = {
            'client_id': self.app_id,
            'redirect_uri': redirect_uri,
            'scope': 'whatsapp_business_messaging,whatsapp_business_management,pages_show_list,business_management',
            'response_type': 'code'
        }
        
        oauth_url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
        logger.info(f"URL OAuth gerada: {oauth_url}")
        return oauth_url
    
    def exchange_code_for_token(self, code, redirect_uri):
        """Troca código OAuth por token de acesso"""
        try:
            params = {
                'client_id': self.app_id,
                'redirect_uri': redirect_uri,
                'client_secret': self.app_secret,
                'code': code
            }
            
            token_url = f"https://graph.facebook.com/v18.0/oauth/access_token?{urlencode(params)}"
            
            response = requests.get(token_url, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Adicionar timestamp de criação e expiração
                now = datetime.now()
                expires_in = token_data.get('expires_in', 3600)  # Default 1 hora
                
                enhanced_token_data = {
                    'access_token': token_data.get('access_token'),
                    'expires_in': expires_in,
                    'created_at': now.isoformat(),
                    'expires_at': (now + timedelta(seconds=expires_in)).isoformat(),
                    'token_type': token_data.get('token_type', 'Bearer'),
                    'raw_response': token_data
                }
                
                # Salvar token no banco
                db_manager.set_config(
                    'whatsapp_token',
                    enhanced_token_data,
                    'Token de acesso WhatsApp obtido via OAuth'
                )
                
                logger.info(f"Token WhatsApp salvo com sucesso (expira em {expires_in}s)")
                
                # Tentar obter token de longa duração
                long_lived_token = self.get_long_lived_token(token_data.get('access_token'))
                if long_lived_token:
                    logger.info("Token de longa duração obtido com sucesso")
                
                return {
                    "success": True,
                    "token_data": enhanced_token_data
                }
            else:
                logger.error(f"Erro ao obter token: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Erro ao trocar código por token: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
    
    def get_access_token(self):
        """Busca token de acesso atual do banco (com renovação automática)"""
        try:
            # Verificar e renovar token se necessário
            if not self.refresh_token_if_needed():
                logger.error("Token não disponível ou expirado - autorização necessária")
                return None
            
            token_data = db_manager.get_config('whatsapp_token')
            if token_data and 'access_token' in token_data:
                return token_data['access_token']
            else:
                logger.warning("Token WhatsApp não encontrado no banco")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao buscar token: {e}")
            return None
    
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
    
    def send_text_message(self, to_phone_number, message_text):
        """Envia mensagem de texto pelo WhatsApp"""
        try:
            # Buscar token de acesso
            access_token = self.get_access_token()
            if not access_token:
                logger.error("Token de acesso WhatsApp não disponível")
                return {
                    "success": False,
                    "error": "Token não disponível"
                }
            
            # Configurar headers
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Configurar payload
            payload = {
                "messaging_product": "whatsapp",
                "to": to_phone_number,
                "type": "text",
                "text": {
                    "body": message_text
                }
            }
            
            logger.info(f"Enviando mensagem para {to_phone_number}: {message_text[:50]}...")
            
            # Fazer requisição
            response = requests.post(
                self.messages_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Mensagem enviada com sucesso para {to_phone_number}")
                
                return {
                    "success": True,
                    "message_id": result.get('messages', [{}])[0].get('id'),
                    "raw_response": result
                }
            else:
                logger.error(f"Erro ao enviar mensagem: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "raw_response": response.text
                }
                
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem WhatsApp: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_outgoing_message(self, contact_id, message_text):
        """Processa envio de mensagem e salva resultado no banco"""
        logger.info(f"Processando envio para {contact_id}: {message_text[:50]}...")
        
        # Enviar mensagem
        result = self.send_text_message(contact_id, message_text)
        
        if result["success"]:
            # Salvar como message_sent (confirmado) no banco
            try:
                db_manager.save_webhook_event(
                    event_type="message_sent",
                    event_data={
                        "type": "text",
                        "from": "bot",
                        "to": contact_id,
                        "text": message_text,
                        "message_id": result.get("message_id"),
                        "status": "sent",
                        "whatsapp_raw": result.get("raw_response")
                    }
                )
                
                logger.info(f"Envio registrado no banco para {contact_id}")
                return True
                
            except Exception as e:
                logger.error(f"Erro ao registrar envio no banco: {e}")
                return True  # Mensagem foi enviada mesmo que não tenha salvado
        else:
            logger.error(f"Falha ao enviar mensagem: {result.get('error', 'Erro desconhecido')}")
            
            # Salvar falha no banco
            try:
                db_manager.save_webhook_event(
                    event_type="message_failed",
                    event_data={
                        "type": "text",
                        "from": "bot",
                        "to": contact_id,
                        "text": message_text,
                        "status": "failed",
                        "error": result.get("error"),
                        "whatsapp_raw": result.get("raw_response")
                    }
                )
            except:
                pass
            
            return False

# Instância global do serviço WhatsApp
whatsapp_service = WhatsAppService() 