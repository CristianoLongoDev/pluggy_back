#!/usr/bin/env python3
"""
Script para testar a detecção de ambiente e configuração do banco MySQL
"""

import os
import socket
from config import detect_environment, ENVIRONMENT, DB_HOST, DB_PORT, DB_NAME

def test_environment_detection():
    """Testa a detecção de ambiente"""
    print("=== Teste de Detecção de Ambiente ===")
    print(f"Hostname: {socket.gethostname()}")
    print(f"KUBERNETES_SERVICE_HOST: {os.getenv('KUBERNETES_SERVICE_HOST', 'Não definido')}")
    print(f"KUBERNETES_PORT: {os.getenv('KUBERNETES_PORT', 'Não definido')}")
    print(f"/.dockerenv existe: {os.path.exists('/.dockerenv')}")
    
    detected_env = detect_environment()
    print(f"Ambiente detectado: {detected_env}")
    print(f"Ambiente configurado: {ENVIRONMENT}")
    print()

def test_database_config():
    """Testa a configuração do banco de dados"""
    print("=== Configuração do Banco de Dados ===")
    print(f"DB_HOST: {DB_HOST}")
    print(f"DB_PORT: {DB_PORT}")
    print(f"DB_NAME: {DB_NAME}")
    print()

def test_connection():
    """Testa a conexão com o banco"""
    print("=== Teste de Conexão ===")
    try:
        from database import db_manager
        if db_manager.connect():
            print("✅ Conexão com o banco estabelecida com sucesso!")
            print(f"Status da conexão: {db_manager.get_connection_status()}")
            db_manager.disconnect()
        else:
            print("❌ Falha ao conectar com o banco")
    except Exception as e:
        print(f"❌ Erro ao testar conexão: {e}")
    print()

if __name__ == "__main__":
    test_environment_detection()
    test_database_config()
    test_connection() 