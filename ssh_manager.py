#!/usr/bin/env python3
"""
SSH Manager for Ubiquiti EdgeSwitch/UniFi switches.
Handles connection, command execution, and output capture.
"""

import paramiko
import time
import os
import stat
import json
import base64
from pathlib import Path
from typing import Optional, List, Tuple
from cryptography.fernet import Fernet
from getpass import getpass


class SSHManager:
    """Manages SSH connections to Ubiquiti switches."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.script_dir = Path(__file__).parent
        self.config_file = config_path or self.script_dir / "config.json"
        self.key_file = self.script_dir / ".ssh_key"
        
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.shell = None
        self.hostname: str = ""
        self.username: str = ""
        self.port: int = 22
        self.timeout: int = 10
        
        # Settings
        self.command_delay: float = 1.0
        self.response_timeout: float = 3.0
        
    # =========================================================================
    # Encryption methods
    # =========================================================================
    
    def _generate_key(self) -> bytes:
        """Generate and save an encryption key."""
        key = Fernet.generate_key()
        with open(self.key_file, 'wb') as f:
            f.write(key)
        os.chmod(self.key_file, stat.S_IRUSR | stat.S_IWUSR)
        return key
    
    def _load_key(self) -> bytes:
        """Load encryption key, generate if not exists."""
        try:
            with open(self.key_file, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return self._generate_key()
    
    def encrypt_password(self, password: str) -> str:
        """Encrypt a password."""
        key = self._load_key()
        f = Fernet(key)
        encrypted = f.encrypt(password.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_password(self, encrypted_password: str) -> Optional[str]:
        """Decrypt a password."""
        try:
            key = self._load_key()
            f = Fernet(key)
            decoded = base64.b64decode(encrypted_password.encode())
            return f.decrypt(decoded).decode()
        except Exception:
            return None
    
    # =========================================================================
    # Configuration methods
    # =========================================================================
    
    def create_config(self, hostname: str, username: str, password: str, 
                      port: int = 22) -> bool:
        """Create configuration file with encrypted password."""
        encrypted_password = self.encrypt_password(password)
        
        config = {
            "ssh": {
                "hostname": hostname,
                "username": username,
                "password_encrypted": encrypted_password,
                "port": port,
                "timeout": 10
            },
            "settings": {
                "command_delay": 1.0,
                "response_timeout": 3.0
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
        return True
    
    def load_config(self) -> Tuple[bool, str]:
        """Load configuration from file. Returns (success, message)."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            ssh_config = config['ssh']
            self.hostname = ssh_config['hostname']
            self.username = ssh_config['username']
            self.port = ssh_config.get('port', 22)
            self.timeout = ssh_config.get('timeout', 10)
            
            # Decrypt password
            if 'password_encrypted' in ssh_config:
                password = self.decrypt_password(ssh_config['password_encrypted'])
                if password is None:
                    return False, "Impossibile decrittare la password"
                self._password = password
            elif 'password' in ssh_config:
                self._password = ssh_config['password']
            else:
                return False, "Password non trovata nella configurazione"
            
            # Load settings
            settings = config.get('settings', {})
            self.command_delay = settings.get('command_delay', 1.0)
            self.response_timeout = settings.get('response_timeout', 3.0)
            
            return True, "Configurazione caricata"
            
        except FileNotFoundError:
            return False, f"File configurazione non trovato: {self.config_file}"
        except json.JSONDecodeError as e:
            return False, f"Errore nel file di configurazione: {e}"
        except KeyError as e:
            return False, f"Chiave mancante nella configurazione: {e}"
    
    def config_exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_file.exists()
    
    # =========================================================================
    # Connection methods
    # =========================================================================
    
    def connect(self) -> Tuple[bool, str]:
        """
        Connect to the switch and enter CLI mode.
        Returns (success, message).
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.ssh_client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self._password,
                timeout=self.timeout
            )
            
            # Open interactive shell
            self.shell = self.ssh_client.invoke_shell()
            time.sleep(2)
            
            # Clear initial buffer
            if self.shell.recv_ready():
                self.shell.recv(65536)
            
            # Enter CLI mode
            self._send_command("cli", wait_prompt=False)
            time.sleep(1)
            self._send_command("enable", wait_prompt=False)
            time.sleep(0.5)
            
            return True, f"Connesso a {self.hostname}"
            
        except paramiko.AuthenticationException:
            return False, "Autenticazione fallita. Controlla username e password."
        except paramiko.SSHException as e:
            return False, f"Errore SSH: {e}"
        except Exception as e:
            return False, f"Errore di connessione: {e}"
    
    def disconnect(self) -> None:
        """Disconnect from the switch."""
        if self.shell:
            try:
                self._send_command("exit", wait_prompt=False)
                time.sleep(0.3)
                self._send_command("exit", wait_prompt=False)
            except Exception:
                pass
            self.shell.close()
            self.shell = None
        
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
    
    def is_connected(self) -> bool:
        """Check if connected to switch."""
        return self.shell is not None and self.ssh_client is not None
    
    # =========================================================================
    # Command execution methods
    # =========================================================================
    
    def _send_command(self, command: str, wait_prompt: bool = True) -> str:
        """
        Send a single command and return the response.
        """
        if not self.shell:
            raise RuntimeError("Non connesso allo switch")
        
        self.shell.send(command + "\n")
        time.sleep(self.command_delay)
        
        response = ""
        start_time = time.time()
        
        while time.time() - start_time < self.response_timeout:
            if self.shell.recv_ready():
                data = self.shell.recv(65536).decode('utf-8', errors='ignore')
                response += data
                if not wait_prompt:
                    break
                # Check for prompt
                if response.strip().endswith(('#', '>', ')')):
                    break
            time.sleep(0.1)
        
        return response
    
    def _send_command_long(self, command: str, timeout: float = 10.0) -> str:
        """
        Send command expecting long output (like show running-config).
        Handles --More-- prompts.
        """
        if not self.shell:
            raise RuntimeError("Non connesso allo switch")
        
        self.shell.send(command + "\n")
        
        response = ""
        start_time = time.time()
        last_data_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.shell.recv_ready():
                data = self.shell.recv(65536).decode('utf-8', errors='ignore')
                response += data
                last_data_time = time.time()
                
                # Handle --More-- prompt
                if '--More--' in data or '--more--' in data.lower():
                    self.shell.send(" ")  # Space to continue
                    time.sleep(0.2)
                    continue
                
            else:
                # No data available
                if time.time() - last_data_time > 2.0:
                    # No new data for 2 seconds, assume complete
                    break
                time.sleep(0.1)
        
        return response
    
    def execute_command(self, command: str) -> str:
        """Execute a single command and return output."""
        return self._send_command(command)
    
    def execute_commands(self, commands: List[str]) -> List[str]:
        """Execute multiple commands and return list of outputs."""
        results = []
        for cmd in commands:
            result = self._send_command(cmd)
            results.append(result)
        return results
    
    # =========================================================================
    # High-level methods for switch data retrieval
    # =========================================================================
    
    def get_running_config(self) -> str:
        """Retrieve running configuration from switch."""
        return self._send_command_long("show running-config", timeout=30.0)
    
    def get_interfaces_status(self) -> str:
        """Retrieve interface status from switch."""
        return self._send_command_long("show interfaces status all", timeout=15.0)
    
    def get_port_channel_brief(self) -> str:
        """Retrieve port-channel/LAG summary from switch."""
        return self._send_command_long("show port-channel brief", timeout=10.0)
    
    def enter_config_mode(self) -> bool:
        """Enter configuration mode."""
        response = self._send_command("configure")
        return "config" in response.lower() or "(Config)" in response
    
    def exit_config_mode(self) -> bool:
        """Exit configuration mode."""
        self._send_command("exit", wait_prompt=False)
        return True
    
    def apply_mirroring_config(self, commands: List[str]) -> Tuple[bool, str]:
        """
        Apply mirroring configuration commands.
        
        Args:
            commands: List of commands (without cli/enable/config prefixes)
        
        Returns:
            (success, output)
        """
        try:
            # Enter config mode
            self.enter_config_mode()
            time.sleep(0.5)
            
            output_lines = []
            for cmd in commands:
                result = self._send_command(cmd)
                output_lines.append(f">>> {cmd}")
                if result.strip():
                    output_lines.append(result.strip())
            
            # Exit config mode
            self.exit_config_mode()
            
            return True, "\n".join(output_lines)
            
        except Exception as e:
            return False, f"Errore durante l'applicazione: {e}"


# =============================================================================
# Interactive configuration setup
# =============================================================================

def setup_config_interactive() -> Optional[SSHManager]:
    """Interactive setup for SSH configuration."""
    print("\n=== CONFIGURAZIONE SSH ===\n")
    
    hostname = input("IP del dispositivo: ").strip()
    if not hostname:
        print("IP non valido")
        return None
    
    username = input("Username [admin]: ").strip() or "admin"
    password = getpass("Password: ").strip()
    if not password:
        print("Password non valida")
        return None
    
    port_str = input("Porta SSH [22]: ").strip() or "22"
    try:
        port = int(port_str)
    except ValueError:
        port = 22
    
    manager = SSHManager()
    manager.create_config(hostname, username, password, port)
    
    print("\n✓ Configurazione salvata e crittografata")
    return manager


if __name__ == "__main__":
    # Test connection
    manager = SSHManager()
    
    if not manager.config_exists():
        manager = setup_config_interactive()
        if not manager:
            exit(1)
    
    success, msg = manager.load_config()
    if not success:
        print(f"Errore: {msg}")
        exit(1)
    
    print(f"Connessione a {manager.hostname}...")
    success, msg = manager.connect()
    
    if success:
        print(f"✓ {msg}")
        print("\nRecupero configurazione...")
        config = manager.get_running_config()
        print(f"Ricevuti {len(config)} caratteri")
        manager.disconnect()
        print("✓ Disconnesso")
    else:
        print(f"✗ {msg}")
