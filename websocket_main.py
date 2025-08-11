#!/usr/bin/env python3
"""
WebSocket Main Server
Inicia servidor WebSocket e notificador em paralelo
"""

import asyncio
import signal
import logging
from websocket_server import websocket_server
from websocket_notifier import start_notifier, stop_notifier

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebSocketMain:
    def __init__(self):
        self.running = False
        
    async def start_services(self):
        """Inicia todos os serviços WebSocket"""
        try:
            logger.info("🚀 Iniciando serviços WebSocket...")
            
            # Iniciar notificador em thread separada
            start_notifier()
            
            # Iniciar servidor WebSocket (principal)
            await websocket_server.start_server()
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar serviços: {e}")
            raise
    
    def handle_shutdown(self, signum, frame):
        """Manipula sinais de shutdown"""
        logger.info(f"📡 Recebido sinal {signum}, iniciando shutdown...")
        self.running = False
        stop_notifier()
    
    async def main(self):
        """Função principal"""
        # Configurar handlers de sinal
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        self.running = True
        
        try:
            logger.info("🌐 Iniciando WebSocket Server...")
            await self.start_services()
            
        except KeyboardInterrupt:
            logger.info("🛑 Interrompido pelo usuário")
        except Exception as e:
            logger.error(f"❌ Erro fatal: {e}")
        finally:
            logger.info("🔚 Finalizando serviços...")
            stop_notifier()

if __name__ == "__main__":
    # Rodar servidor
    main_server = WebSocketMain()
    asyncio.run(main_server.main())