#!/usr/bin/env python3
"""
Script Generator for Ubiquiti Port Mirroring configuration.
Generates reusable bash scripts and command files.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config_parser import SwitchConfig


class ScriptGenerator:
    """Generates reusable configuration scripts."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.script_dir = Path(__file__).parent
        self.output_dir = output_dir or self.script_dir / "generated"
        
        # Create output directory if needed
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_timestamp(self) -> str:
        """Generate timestamp string for filenames."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def generate_human_timestamp(self) -> str:
        """Generate human-readable timestamp for comments."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # =========================================================================
    # Bash script generation
    # =========================================================================
    
    def generate_bash_script(
        self,
        commands: List[str],
        device_ip: str,
        username: str = "admin",
        port: int = 22,
        config: Optional[SwitchConfig] = None,
        description: str = ""
    ) -> Path:
        """
        Generate a bash script to apply mirroring configuration.
        
        Args:
            commands: List of configuration commands (without cli/enable/config prefixes)
            device_ip: Switch IP address
            username: SSH username
            port: SSH port
            config: Optional switch config for additional info
            description: Optional description of what this script does
        
        Returns:
            Path to generated script
        """
        timestamp = self.generate_timestamp()
        human_ts = self.generate_human_timestamp()
        
        filename = f"mirror_config_{timestamp}.sh"
        filepath = self.output_dir / filename
        
        # Build device info
        device_info = device_ip
        if config and config.system_info.hostname:
            device_info = f"{config.system_info.hostname} ({device_ip})"
        
        model_info = ""
        if config and config.system_info.description:
            model_info = config.system_info.description.split(",")[0]
        
        # Build commands block
        cli_commands = [
            "cli",
            "enable",
            "configure",
            *commands,
            "exit",
            "exit",
            "exit"
        ]
        commands_block = "\n".join(cli_commands)
        
        # Build script content
        script_content = f'''#!/bin/bash
# ============================================================
# Ubiquiti Port Mirroring Configuration Script
# ============================================================
# Generated: {human_ts}
# Device: {device_info}
{f"# Model: {model_info}" if model_info else ""}
{f"# Description: {description}" if description else ""}
# ============================================================
#
# This script applies port mirroring configuration via SSH.
#
# REQUIREMENTS:
#   - sshpass installed (brew install sshpass / apt install sshpass)
#   - SSH access to the device
#
# USAGE:
#   ./mirror_config_{timestamp}.sh              # Will prompt for password
#   ./mirror_config_{timestamp}.sh "password"   # Password as argument
#
# ============================================================

set -e

# Device configuration
DEVICE_IP="{device_ip}"
USERNAME="{username}"
SSH_PORT={port}

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

echo -e "${{YELLOW}}============================================================${{NC}}"
echo -e "${{YELLOW}} Ubiquiti Port Mirroring Configuration${{NC}}"
echo -e "${{YELLOW}}============================================================${{NC}}"
echo ""
echo "Device: $DEVICE_IP"
echo "User:   $USERNAME"
echo ""

# Get password
if [ -z "$1" ]; then
    read -sp "Enter SSH password for $USERNAME@$DEVICE_IP: " PASSWORD
    echo ""
else
    PASSWORD="$1"
fi

if [ -z "$PASSWORD" ]; then
    echo -e "${{RED}}Error: Password is required${{NC}}"
    exit 1
fi

# Check if sshpass is available
if ! command -v sshpass &> /dev/null; then
    echo -e "${{RED}}Error: sshpass is not installed${{NC}}"
    echo "Install with: brew install sshpass (macOS) or apt install sshpass (Linux)"
    exit 1
fi

# Commands to execute
read -r -d '' COMMANDS << 'CMDEOF' || true
{commands_block}
CMDEOF

echo -e "${{YELLOW}}Connecting to $DEVICE_IP...${{NC}}"
echo ""

# Execute commands via SSH
if sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \\
    -p $SSH_PORT $USERNAME@$DEVICE_IP "$COMMANDS" 2>/dev/null; then
    echo ""
    echo -e "${{GREEN}}============================================================${{NC}}"
    echo -e "${{GREEN}} Configuration applied successfully!${{NC}}"
    echo -e "${{GREEN}}============================================================${{NC}}"
else
    echo ""
    echo -e "${{RED}}============================================================${{NC}}"
    echo -e "${{RED}} Error applying configuration${{NC}}"
    echo -e "${{RED}}============================================================${{NC}}"
    exit 1
fi
'''
        
        # Write script
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(filepath, 0o755)
        
        return filepath
    
    # =========================================================================
    # Command file generation
    # =========================================================================
    
    def generate_command_file(
        self,
        commands: List[str],
        device_ip: str,
        config: Optional[SwitchConfig] = None,
        description: str = "",
        include_cli_prefix: bool = True
    ) -> Path:
        """
        Generate a text file with commands only.
        
        Args:
            commands: List of configuration commands
            device_ip: Switch IP address
            config: Optional switch config for additional info
            description: Optional description
            include_cli_prefix: Include cli/enable/config prefix commands
        
        Returns:
            Path to generated file
        """
        timestamp = self.generate_timestamp()
        human_ts = self.generate_human_timestamp()
        
        filename = f"mirror_commands_{timestamp}.txt"
        filepath = self.output_dir / filename
        
        # Build device info
        device_info = device_ip
        if config and config.system_info.hostname:
            device_info = f"{config.system_info.hostname} ({device_ip})"
        
        # Build content
        lines = [
            "# ============================================================",
            "# Ubiquiti Port Mirroring Commands",
            "# ============================================================",
            f"# Generated: {human_ts}",
            f"# Device: {device_info}",
        ]
        
        if description:
            lines.append(f"# Description: {description}")
        
        lines.extend([
            "# ============================================================",
            "#",
            "# To apply these commands manually:",
            "#   1. SSH to the device",
            "#   2. Enter: cli",
            "#   3. Enter: enable", 
            "#   4. Enter: configure",
            "#   5. Execute the commands below",
            "#   6. Enter: exit (3 times to logout)",
            "#",
            "# ============================================================",
            "",
        ])
        
        if include_cli_prefix:
            lines.extend([
                "# === CLI Access Commands ===",
                "cli",
                "enable",
                "configure",
                "",
                "# === Mirroring Configuration ===",
            ])
        
        lines.extend(commands)
        
        if include_cli_prefix:
            lines.extend([
                "",
                "# === Exit Commands ===",
                "exit",
                "exit",
                "exit",
            ])
        
        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        
        return filepath
    
    # =========================================================================
    # Python script generation (alternative to bash)
    # =========================================================================
    
    def generate_python_script(
        self,
        commands: List[str],
        device_ip: str,
        username: str = "admin",
        port: int = 22,
        config: Optional[SwitchConfig] = None,
        description: str = ""
    ) -> Path:
        """
        Generate a Python script to apply mirroring configuration.
        Uses paramiko, doesn't require sshpass.
        
        Returns:
            Path to generated script
        """
        timestamp = self.generate_timestamp()
        human_ts = self.generate_human_timestamp()
        
        filename = f"mirror_config_{timestamp}.py"
        filepath = self.output_dir / filename
        
        # Build device info
        device_info = device_ip
        if config and config.system_info.hostname:
            device_info = f"{config.system_info.hostname} ({device_ip})"
        
        # Format commands as Python list
        commands_str = ",\n        ".join([f'"{cmd}"' for cmd in commands])
        
        script_content = f'''#!/usr/bin/env python3
"""
Ubiquiti Port Mirroring Configuration Script

Generated: {human_ts}
Device: {device_info}
{f"Description: {description}" if description else ""}

Requirements: pip install paramiko
Usage: python mirror_config_{timestamp}.py
"""

import paramiko
import time
import sys
from getpass import getpass


# Configuration
DEVICE_IP = "{device_ip}"
USERNAME = "{username}"
SSH_PORT = {port}

# Commands to execute
COMMANDS = [
    "cli",
    "enable",
    "configure",
    {commands_str},
    "exit",
    "exit",
    "exit",
]


def apply_config(password: str) -> bool:
    """Apply configuration to device."""
    try:
        print(f"Connecting to {{DEVICE_IP}}...")
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=DEVICE_IP,
            port=SSH_PORT,
            username=USERNAME,
            password=password,
            timeout=10
        )
        
        shell = ssh.invoke_shell()
        time.sleep(2)
        
        # Clear buffer
        if shell.recv_ready():
            shell.recv(65536)
        
        print("Connected. Applying configuration...")
        print()
        
        for cmd in COMMANDS:
            print(f"  >>> {{cmd}}")
            shell.send(cmd + "\\n")
            time.sleep(1)
            
            if shell.recv_ready():
                response = shell.recv(4096).decode('utf-8', errors='ignore')
                for line in response.strip().split("\\n")[:2]:
                    if line.strip() and not line.strip().startswith("("):
                        print(f"      {{line.strip()}}")
        
        shell.close()
        ssh.close()
        
        print()
        print("=" * 50)
        print(" Configuration applied successfully!")
        print("=" * 50)
        return True
        
    except paramiko.AuthenticationException:
        print("ERROR: Authentication failed")
        return False
    except Exception as e:
        print(f"ERROR: {{e}}")
        return False


def main():
    print("=" * 50)
    print(" Ubiquiti Port Mirroring Configuration")
    print("=" * 50)
    print()
    print(f"Device: {{DEVICE_IP}}")
    print(f"User:   {{USERNAME}}")
    print()
    
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass(f"Enter SSH password for {{USERNAME}}@{{DEVICE_IP}}: ")
    
    if not password:
        print("Error: Password is required")
        sys.exit(1)
    
    success = apply_config(password)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
'''
        
        # Write script
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(filepath, 0o755)
        
        return filepath
    
    # =========================================================================
    # Generate all formats
    # =========================================================================
    
    def generate_all(
        self,
        commands: List[str],
        device_ip: str,
        username: str = "admin",
        port: int = 22,
        config: Optional[SwitchConfig] = None,
        description: str = ""
    ) -> dict:
        """
        Generate all script formats.
        
        Returns:
            Dict with paths: {'bash': Path, 'python': Path, 'commands': Path}
        """
        bash_path = self.generate_bash_script(
            commands, device_ip, username, port, config, description
        )
        
        python_path = self.generate_python_script(
            commands, device_ip, username, port, config, description
        )
        
        cmd_path = self.generate_command_file(
            commands, device_ip, config, description
        )
        
        return {
            'bash': bash_path,
            'python': python_path,
            'commands': cmd_path
        }


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    generator = ScriptGenerator()
    
    # Test commands
    commands = [
        "no monitor session 1",
        "monitor session 1 destination interface 0/3",
        "monitor session 1 source interface 0/4",
        "monitor session 1 source interface 0/8",
        "monitor session 1 source interface 0/17",
        "monitor session 1 source interface 0/18",
        "monitor session 1 mode",
    ]
    
    # Generate all
    paths = generator.generate_all(
        commands=commands,
        device_ip="192.168.40.243",
        username="admin",
        description="Port mirroring for network monitoring"
    )
    
    print("Generated files:")
    for fmt, path in paths.items():
        print(f"  {fmt}: {path}")
