#!/usr/bin/env python3
"""
Script automatico per connessione SSH e invio comandi sequenziali
Requisiti: pip install paramiko
"""

import paramiko
import time
import os
import sys
import json
import base64
import stat
from pathlib import Path
from cryptography.fernet import Fernet
from getpass import getpass

class SSHCommandExecutor:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.config_file = self.script_dir / "config.json"
        self.commands_file = self.script_dir / "comandi.txt"
        self.key_file = self.script_dir / ".ssh_key"
        
    def generate_key(self):
        """Genera e salva una chiave di crittografia"""
        key = Fernet.generate_key()
        with open(self.key_file, 'wb') as f:
            f.write(key)
        # Rende il file leggibile solo dal proprietario
        os.chmod(self.key_file, stat.S_IRUSR | stat.S_IWUSR)
        return key
    
    def load_key(self):
        """Carica la chiave di crittografia"""
        try:
            with open(self.key_file, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return self.generate_key()
    
    def encrypt_password(self, password):
        """Crittografa una password"""
        key = self.load_key()
        f = Fernet(key)
        encrypted_password = f.encrypt(password.encode())
        return base64.b64encode(encrypted_password).decode()
    
    def decrypt_password(self, encrypted_password):
        """Decrittografa una password"""
        try:
            key = self.load_key()
            f = Fernet(key)
            decoded_password = base64.b64decode(encrypted_password.encode())
            return f.decrypt(decoded_password).decode()
        except Exception:
            return None
        
    def create_config_file(self):
        """Crea file di configurazione di esempio"""
        print("=== CONFIGURAZIONE INIZIALE ===")
        print("Inserisci le credenziali SSH (saranno crittografate)")
        
        hostname = input("IP del server SSH: ").strip()
        username = input("Username: ").strip()
        password = getpass("Password (nascosta): ").strip()
        port = input("Porta SSH [22]: ").strip() or "22"
        
        # Crittografa la password
        encrypted_password = self.encrypt_password(password)
        
        config_template = {
            "ssh": {
                "hostname": hostname,
                "username": username,
                "password_encrypted": encrypted_password,
                "port": int(port),
                "timeout": 10
            },
            "settings": {
                "command_delay": 1.0,
                "response_timeout": 2.0,
                "max_response_chars": 200
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as file:
            json.dump(config_template, file, indent=4, ensure_ascii=False)
        
        # Rende il file leggibile solo dal proprietario
        os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
        
        print(f"✓ File di configurazione creato: {self.config_file}")
        print("✓ Password crittografata e file protetto")
        return True
    
    def create_sample_commands_file(self):
        """Crea file di esempio comandi.txt"""
        sample_commands = """# File comandi.txt - Lista dei comandi da eseguire
# Linee che iniziano con # sono commenti e vengono ignorate
# I comandi vengono eseguiti dopo: cli -> enable -> config

show version
show interfaces brief
show running-config
show ip route
show system status
# Aggiungi altri comandi qui...
exit
"""
        with open(self.commands_file, 'w', encoding='utf-8') as file:
            file.write(sample_commands)
        
        print(f"File comandi di esempio creato: {self.commands_file}")
        return True
    
    def load_config(self):
        """Carica configurazione da file JSON"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            # Verifica se la password è crittografata o in chiaro
            ssh_config = config['ssh']
            if 'password_encrypted' in ssh_config:
                # Password crittografata - decrittografa
                encrypted_password = ssh_config['password_encrypted']
                decrypted_password = self.decrypt_password(encrypted_password)
                if decrypted_password is None:
                    print("❌ ERRORE: Impossibile decrittografare la password")
                    print("Il file di configurazione potrebbe essere danneggiato")
                    return None
                ssh_config['password'] = decrypted_password
            elif 'password' in ssh_config:
                # Password in chiaro - convertila in crittografata
                print("⚠️  Password trovata in chiaro, la sto crittografando...")
                plain_password = ssh_config['password']
                encrypted_password = self.encrypt_password(plain_password)
                ssh_config['password_encrypted'] = encrypted_password
                del ssh_config['password']  # Rimuovi password in chiaro
                
                # Salva il file aggiornato
                with open(self.config_file, 'w', encoding='utf-8') as file:
                    json.dump(config, file, indent=4, ensure_ascii=False)
                os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
                ssh_config['password'] = plain_password  # Per l'uso corrente
                print("✓ Password crittografata e file aggiornato")
            
            return config
        except FileNotFoundError:
            print(f"ERRORE: File configurazione '{self.config_file}' non trovato!")
            return None
        except json.JSONDecodeError as e:
            print(f"ERRORE: File configurazione non valido - {e}")
            return None
    
    def load_commands(self):
        """Carica comandi da file txt"""
        try:
            with open(self.commands_file, 'r', encoding='utf-8') as file:
                commands = []
                for line in file:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        commands.append(line)
                return commands
        except FileNotFoundError:
            print(f"ERRORE: File comandi '{self.commands_file}' non trovato!")
            return None
    
    def send_command_and_wait(self, shell, command, delay=1.0, timeout=2.0):
        """Invia comando e attende risposta"""
        print(f"  → {command}")
        shell.send(command + "\n")
        time.sleep(delay)
        
        # Lettura risposta con timeout
        start_time = time.time()
        response = ""
        while time.time() - start_time < timeout:
            if shell.recv_ready():
                data = shell.recv(4096).decode('utf-8', errors='ignore')
                response += data
                break
            time.sleep(0.1)
        
        if response.strip():
            # Mostra solo le prime righe della risposta per brevità
            lines = response.strip().split('\n')
            display_lines = lines[:3] if len(lines) > 3 else lines
            for line in display_lines:
                if line.strip():
                    print(f"    ← {line.strip()}")
            if len(lines) > 3:
                print(f"    ... (e altre {len(lines)-3} righe)")
        
        return response
    
    def execute_ssh_commands(self):
        """Esegue la sequenza completa di comandi SSH"""
        
        # Caricamento configurazione
        config = self.load_config()
        if not config:
            return False
        
        ssh_config = config['ssh']
        settings = config.get('settings', {})
        
        # Caricamento comandi
        commands = self.load_commands()
        if not commands:
            return False
        
        try:
            print(f"Connessione SSH a {ssh_config['hostname']}:{ssh_config.get('port', 22)}...")
            print(f"Utente: {ssh_config['username']}")
            
            # Creazione e connessione client SSH
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh_client.connect(
                hostname=ssh_config['hostname'],
                port=ssh_config.get('port', 22),
                username=ssh_config['username'],
                password=ssh_config['password'],
                timeout=ssh_config.get('timeout', 10)
            )
            
            # Apertura shell interattiva
            shell = ssh_client.invoke_shell()
            time.sleep(2)
            
            # Pulizia buffer iniziale
            if shell.recv_ready():
                shell.recv(4096)
            
            print("✓ Connessione SSH stabilita\n")
            
            # Sequenza comandi obbligatoria
            print("=== SEQUENZA INIZIALE ===")
            command_delay = settings.get('command_delay', 1.0)
            response_timeout = settings.get('response_timeout', 2.0)
            
            self.send_command_and_wait(shell, "cli", command_delay, response_timeout)
            self.send_command_and_wait(shell, "enable", command_delay, response_timeout)
            self.send_command_and_wait(shell, "config", command_delay, response_timeout)
            
            print(f"\n=== ESECUZIONE COMANDI DAL FILE ({len(commands)} comandi) ===")
            
            # Esecuzione comandi dal file
            for i, command in enumerate(commands, 1):
                print(f"[{i}/{len(commands)}] Esecuzione comando:")
                self.send_command_and_wait(shell, command, command_delay, response_timeout)
                print()  # Riga vuota per separare i comandi
            
            print("✓ Tutti i comandi sono stati eseguiti con successo!")
            
            # Chiusura connessione
            shell.close()
            ssh_client.close()
            print("✓ Connessione SSH chiusa")
            
            return True
            
        except paramiko.AuthenticationException:
            print("❌ ERRORE: Autenticazione fallita. Controlla username e password in config.json")
            return False
        except paramiko.SSHException as ssh_error:
            print(f"❌ ERRORE SSH: {ssh_error}")
            return False
        except Exception as e:
            print(f"❌ ERRORE generico: {e}")
            return False
    
    def run(self):
        """Esegue lo script principale"""
        print("=== SSH Command Executor - Modalità Automatica ===\n")
        
        # Verifica e creazione file necessari
        files_created = False
        
        if not self.config_file.exists():
            self.create_config_file()
            files_created = True
        
        if not self.commands_file.exists():
            self.create_sample_commands_file()
            files_created = True
        
        if files_created:
            print("\n" + "="*60)
            print("CONFIGURAZIONE COMPLETATA")
            print("="*60)
            print("✓ Credenziali crittografate e salvate")
            print("✓ File protetti con permessi restrittivi")
            print("1. Modifica 'comandi.txt' se necessario")
            print("2. Riesegui lo script per connetterti")
            print("="*60)
            return
        
        try:
            success = self.execute_ssh_commands()
            if success:
                print("\n🎉 Script completato con successo!")
            else:
                print("\n❌ Script terminato con errori.")
                sys.exit(1)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Script interrotto dall'utente.")
            sys.exit(0)

def main():
    executor = SSHCommandExecutor()
    executor.run()

if __name__ == "__main__":
    main()
