#!/usr/bin/env python3
"""
Serviço de transcrição de áudio usando OpenAI Whisper
Baixa arquivos de áudio do WhatsApp, converte para MP3 e transcreve
"""

import os
import logging
import requests
import tempfile
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioTranscriptionService:
    def __init__(self):
        # Usar a mesma API key do ChatGPT
        self.api_key = "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"
        self.api_url = "https://api.openai.com/v1/audio/transcriptions"
        self.model = "whisper-1"
        
    def download_audio_file(self, audio_url, access_token=None, timeout=30):
        """
        Baixa arquivo de áudio da URL fornecida (com autenticação WhatsApp)
        """
        try:
            logger.info(f"🎵 Baixando arquivo de áudio: {audio_url[:50]}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Adicionar token de autorização se fornecido (necessário para URLs do WhatsApp)
            if access_token:
                headers['Authorization'] = f'Bearer {access_token}'
                logger.info("🔐 Usando autenticação WhatsApp para download")
            
            response = requests.get(audio_url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Criar arquivo temporário
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
            
            # Baixar em chunks
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            
            temp_file.close()
            
            logger.info(f"✅ Áudio baixado com sucesso: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"❌ Erro ao baixar áudio: {e}")
            return None
    
    def convert_to_mp3(self, input_file, output_file=None):
        """
        Converte arquivo de áudio para MP3 usando ffmpeg
        """
        try:
            if not output_file:
                output_file = input_file.replace('.tmp', '.mp3')
            
            logger.info(f"🔄 Convertendo áudio para MP3...")
            
            # Verificar se ffmpeg está disponível
            try:
                subprocess.run(['ffmpeg', '-version'], 
                             capture_output=True, check=True, timeout=5)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                logger.error("❌ ffmpeg não encontrado. Tentando sem conversão...")
                # Se não tem ffmpeg, tentar usar o arquivo original
                return input_file
            
            # Comando ffmpeg para conversão
            cmd = [
                'ffmpeg', '-i', input_file,
                '-acodec', 'mp3',
                '-ar', '16000',  # 16kHz sample rate (recomendado para Whisper)
                '-ac', '1',      # Mono
                '-y',            # Sobrescrever arquivo se existir
                output_file
            ]
            
            # Executar conversão com timeout
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60  # 1 minuto timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Conversão concluída: {output_file}")
                
                # Remover arquivo original
                try:
                    os.unlink(input_file)
                except:
                    pass
                    
                return output_file
            else:
                logger.error(f"❌ Erro na conversão ffmpeg: {result.stderr}")
                # Retornar arquivo original se conversão falhar
                return input_file
                
        except subprocess.TimeoutExpired:
            logger.error("⏰ Timeout na conversão de áudio")
            return input_file
        except Exception as e:
            logger.error(f"❌ Erro na conversão: {e}")
            return input_file
    
    def transcribe_audio(self, audio_file_path):
        """
        Transcreve arquivo de áudio usando OpenAI Whisper
        """
        try:
            logger.info(f"🎤 Transcrevendo áudio: {audio_file_path}")
            
            # Verificar se o arquivo existe
            if not os.path.exists(audio_file_path):
                logger.error(f"❌ Arquivo de áudio não encontrado: {audio_file_path}")
                return None
            
            # Verificar tamanho do arquivo (limite OpenAI: 25MB)
            file_size = os.path.getsize(audio_file_path)
            if file_size > 25 * 1024 * 1024:  # 25MB
                logger.error(f"❌ Arquivo muito grande ({file_size/1024/1024:.1f}MB). Limite: 25MB")
                return None
            
            logger.info(f"📊 Tamanho do arquivo: {file_size/1024:.1f}KB")
            
            # Configurar headers para requisição
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # Preparar dados para multipart/form-data
            files = {
                'file': open(audio_file_path, 'rb'),
                'model': (None, self.model),
                'language': (None, 'pt')  # Forçar português
            }
            
            # Fazer requisição para OpenAI Whisper
            response = requests.post(
                self.api_url,
                headers=headers,
                files=files,
                timeout=60
            )
            
            # Fechar arquivo
            files['file'].close()
            
            if response.status_code == 200:
                result = response.json()
                transcription = result.get('text', '').strip()
                
                if transcription:
                    logger.info(f"✅ Transcrição concluída: {transcription[:100]}...")
                    return transcription
                else:
                    logger.warning("⚠️ Transcrição vazia")
                    return None
            else:
                logger.error(f"❌ Erro na API Whisper: {response.status_code} - {response.text}")
                return None
                    
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            return None
        finally:
            # Limpar arquivo temporário
            try:
                if os.path.exists(audio_file_path):
                    os.unlink(audio_file_path)
                    logger.debug(f"🧹 Arquivo temporário removido: {audio_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Erro ao limpar arquivo: {cleanup_error}")
    
    def process_audio_message(self, audio_url, access_token=None):
        """
        Processa mensagem de áudio completa: download -> conversão -> transcrição
        """
        try:
            logger.info(f"🎙️ Iniciando processamento de áudio: {audio_url[:50]}...")
            
            # 1. Baixar arquivo de áudio (com autenticação se fornecida)
            temp_audio_file = self.download_audio_file(audio_url, access_token)
            if not temp_audio_file:
                return None
            
            # 2. Converter para MP3 (se necessário)
            mp3_file = self.convert_to_mp3(temp_audio_file)
            if not mp3_file:
                return None
            
            # 3. Transcrever áudio
            transcription = self.transcribe_audio(mp3_file)
            
            if transcription:
                logger.info(f"🎉 Processamento de áudio concluído com sucesso")
                return {
                    "success": True,
                    "transcription": transcription,
                    "message": "Áudio transcrito com sucesso"
                }
            else:
                logger.error("❌ Falha na transcrição")
                return {
                    "success": False,
                    "error": "Falha na transcrição do áudio",
                    "transcription": None
                }
                
        except Exception as e:
            logger.error(f"❌ Erro no processamento de áudio: {e}")
            return {
                "success": False,
                "error": str(e),
                "transcription": None
            }

# Instância global do serviço
audio_transcription_service = AudioTranscriptionService() 