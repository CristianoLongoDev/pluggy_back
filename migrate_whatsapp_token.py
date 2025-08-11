#!/usr/bin/env python3
"""
Script para migrar o token WhatsApp para a estrutura otimizada

Este script:
1. Verifica o token atual
2. Otimiza removendo campos desnecessários 
3. Inclui phone_number_id e display_phone_number
4. Preserva campos essenciais para funcionamento
"""

import sys
import os
import logging
from datetime import datetime

# Adicionar diretório atual ao path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db_manager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Executa a migração do token WhatsApp"""
    
    print("🔄 Iniciando migração do token WhatsApp...")
    print("=" * 50)
    
    try:
        # Verificar se o banco está habilitado
        if not db_manager.enabled:
            print("❌ Banco de dados não está habilitado!")
            return False
        
        # Buscar token atual
        print("📋 Verificando token atual...")
        current_token = db_manager.get_config('whatsapp_token')
        
        if not current_token:
            print("❌ Token whatsapp_token não encontrado no banco!")
            return False
        
        print(f"✅ Token encontrado com {len(current_token)} campos")
        
        # Mostrar estrutura atual
        print("\n📊 Estrutura atual:")
        for field in sorted(current_token.keys()):
            if field == 'access_token':
                print(f"  - {field}: ***redacted*** ({len(current_token[field])} chars)")
            else:
                value = current_token[field]
                if isinstance(value, str) and len(value) > 50:
                    print(f"  - {field}: {str(value)[:50]}...")
                else:
                    print(f"  - {field}: {value}")
        
        # Verificar se já está otimizado
        if current_token.get("version") == "2.0":
            print("\n✅ Token já está otimizado (versão 2.0)!")
            print("📱 Configuração do telefone:")
            print(f"  - phone_number_id: {current_token.get('phone_number_id', 'Não definido')}")
            print(f"  - display_phone_number: {current_token.get('display_phone_number', 'Não definido')}")
            return True
        
        # Identificar campos que serão removidos
        obsolete_fields = []
        for field in ['created_at', 'expires_in', 'token_type', 'raw_response']:
            if field in current_token:
                obsolete_fields.append(field)
        
        if obsolete_fields:
            print(f"\n🗑️ Campos que serão removidos: {', '.join(obsolete_fields)}")
        
        # Confirmar migração
        print(f"\n⚠️ Esta operação irá:")
        print(f"  1. Remover {len(obsolete_fields)} campos desnecessários")
        print(f"  2. Adicionar phone_number_id: 421769451025047")
        print(f"  3. Adicionar display_phone_number: 555437710014")
        print(f"  4. Marcar como versão 2.0")
        
        confirm = input("\n🤔 Confirma a migração? (s/N): ").lower().strip()
        
        if confirm not in ['s', 'sim', 'y', 'yes']:
            print("❌ Migração cancelada pelo usuário")
            return False
        
        # Executar migração
        print("\n🔄 Executando migração...")
        
        success = db_manager.optimize_whatsapp_token(
            phone_number_id="421769451025047",
            display_phone_number="555437710014"
        )
        
        if success:
            print("\n✅ Migração concluída com sucesso!")
            
            # Verificar resultado
            optimized_token = db_manager.get_config('whatsapp_token')
            
            print(f"\n📊 Nova estrutura ({len(optimized_token)} campos):")
            for field in sorted(optimized_token.keys()):
                if field == 'access_token':
                    print(f"  - {field}: ***redacted*** ({len(optimized_token[field])} chars)")
                else:
                    print(f"  - {field}: {optimized_token[field]}")
            
            print(f"\n🎉 Token otimizado - versão {optimized_token.get('version')}")
            print(f"📅 Otimizado em: {optimized_token.get('optimized_at')}")
            
            return True
        else:
            print("❌ Falha na migração!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro na migração: {e}")
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🚀 Migração concluída! O token está otimizado e pronto para uso.")
        print("\n💡 Próximos passos:")
        print("  1. Faça deploy da aplicação: ./deploy.sh")
        print("  2. Teste os endpoints: /whatsapp/token/status")
        print("  3. Verifique se o WhatsApp está funcionando")
        sys.exit(0)
    else:
        print("\n❌ Migração falhou!")
        sys.exit(1) 