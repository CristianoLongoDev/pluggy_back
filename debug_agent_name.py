#!/usr/bin/env python3
"""Script para debugar agent_name do bot"""

from database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_bot_agent_name():
    """Verifica se os bots têm agent_name configurado"""
    if not db_manager.enabled:
        print("❌ Database não habilitado")
        return
    
    def _check_bots_operation(connection):
        cursor = connection.cursor(dictionary=True)
        
        # Buscar todos os bots
        query = """
            SELECT id, name, agent_name, system_prompt
            FROM bots
            ORDER BY id
        """
        cursor.execute(query)
        bots = cursor.fetchall()
        
        print(f"\n📊 Encontrados {len(bots)} bots:")
        for bot in bots:
            print(f"Bot ID: {bot['id']}")
            print(f"  Nome: {bot['name']}")
            print(f"  Agent Name: '{bot['agent_name']}' ({'VAZIO' if not bot['agent_name'] else 'OK'})")
            print(f"  System Prompt: {len(bot['system_prompt']) if bot['system_prompt'] else 0} chars")
            print("-" * 50)
        
        cursor.close()
        return bots
    
    try:
        return db_manager._execute_with_fresh_connection(_check_bots_operation)
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

if __name__ == "__main__":
    check_bot_agent_name()
