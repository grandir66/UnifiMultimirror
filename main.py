#!/usr/bin/env python3
"""
Ubiquiti Port Mirroring Manager

A tool to configure port mirroring on Ubiquiti UniFi/EdgeSwitch devices via SSH.
Provides an interactive menu interface for viewing port status, configuring
mirroring, and generating reusable configuration scripts.

Usage:
    python main.py
    
Requirements:
    pip install paramiko rich cryptography
"""

import sys
from pathlib import Path
from typing import Optional, List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich import box

from ssh_manager import SSHManager, setup_config_interactive
from config_parser import ConfigParser
from ui import PortMirroringUI
from script_generator import ScriptGenerator


class PortMirroringManager:
    """Main application controller."""
    
    def __init__(self):
        self.console = Console()
        self.ssh_manager = SSHManager()
        self.parser = ConfigParser()
        self.ui = PortMirroringUI()
        self.script_gen = ScriptGenerator()
        
        self.is_connected = False
        self.config_loaded = False
        
        # Pending changes (not yet applied)
        self.pending_destination: Optional[str] = None
        self.pending_sources: List[str] = []
        self.has_pending_changes = False
    
    # =========================================================================
    # Initialization
    # =========================================================================
    
    def initialize(self) -> bool:
        """Initialize the application - always ask for IP and password."""
        self.console.print()
        self.console.print(Panel(
            "[bold]UBIQUITI PORT MIRRORING MANAGER[/bold]\n\n"
            "Gestione port mirroring per switch UniFi/EdgeSwitch",
            style="bold white on blue",
            box=box.DOUBLE
        ))
        self.console.print()
        
        # Always ask for connection details
        return self._ask_connection_details()
    
    def _ask_connection_details(self) -> bool:
        """Ask user for IP and password, then connect."""
        from getpass import getpass
        
        self.console.print("[bold]CONNESSIONE AL DISPOSITIVO[/bold]")
        self.console.print()
        
        # Check if we have saved config
        saved_ip = ""
        if self.ssh_manager.config_exists():
            success, _ = self.ssh_manager.load_config()
            if success:
                saved_ip = self.ssh_manager.hostname
        
        # Ask for IP
        if saved_ip:
            ip_prompt = f"IP del dispositivo [{saved_ip}]"
            ip_input = Prompt.ask(ip_prompt, default=saved_ip)
        else:
            ip_input = Prompt.ask("IP del dispositivo")
        
        if not ip_input or not ip_input.strip():
            self.console.print("[red]IP non valido[/red]")
            return False
        
        ip_address = ip_input.strip()
        
        # Username is always admin
        username = "admin"
        self.console.print(f"[dim]Username: {username}[/dim]")
        
        # Ask for password
        self.console.print()
        password = getpass("Password: ")
        
        if not password:
            self.console.print("[red]Password non valida[/red]")
            return False
        
        # Save config
        self.ssh_manager.create_config(
            hostname=ip_address,
            username=username,
            password=password,
            port=22
        )
        
        # Reload config
        success, msg = self.ssh_manager.load_config()
        if not success:
            self.console.print(f"[red]Errore: {msg}[/red]")
            return False
        
        self.console.print()
        
        # Connect
        return self.connect_to_device()
    
    def connect_to_device(self) -> bool:
        """Connect to the switch and load configuration."""
        self.console.print(f"\n[dim]Connessione a {self.ssh_manager.hostname}...[/dim]")
        
        success, msg = self.ssh_manager.connect()
        if not success:
            self.console.print(f"[red]✗ {msg}[/red]")
            return False
        
        self.is_connected = True
        self.console.print(f"[green]✓ {msg}[/green]")
        
        # Load configuration
        return self.reload_configuration()
    
    def reload_configuration(self) -> bool:
        """Reload configuration from the switch."""
        if not self.is_connected:
            self.console.print("[red]Non connesso al dispositivo[/red]")
            return False
        
        self.console.print("[dim]Recupero configurazione...[/dim]")
        
        try:
            # Get running config
            running_config = self.ssh_manager.get_running_config()
            self.parser.parse_running_config(running_config)
            self.console.print("[green]✓[/green] Running configuration caricata")
            
            # Get interface status
            iface_status = self.ssh_manager.get_interfaces_status()
            self.parser.parse_interfaces_status(iface_status)
            self.console.print("[green]✓[/green] Stato interfacce caricato")
            
            # Get port-channel info
            pc_brief = self.ssh_manager.get_port_channel_brief()
            self.parser.parse_port_channel_brief(pc_brief)
            self.console.print("[green]✓[/green] Configurazione LAG caricata")
            
            # Update UI
            self.ui.set_config(self.parser)
            self.ui.set_device_info(self.ssh_manager.hostname, self.ssh_manager.username)
            
            self.config_loaded = True
            self.console.print()
            
            # Show summary
            dest = self.parser.get_mirroring_destination()
            sources = self.parser.get_mirroring_sources()
            
            if dest:
                self.console.print(
                    f"[dim]Mirroring attivo: Destination=[bold]{dest}[/bold], "
                    f"Sources={len(sources)} porte[/dim]"
                )
            else:
                self.console.print("[dim]Nessun mirroring configurato[/dim]")
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Errore durante il caricamento: {e}[/red]")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the switch."""
        if self.is_connected:
            self.ssh_manager.disconnect()
            self.is_connected = False
            self.console.print("[dim]Disconnesso dal dispositivo[/dim]")
    
    # =========================================================================
    # Main menu handlers
    # =========================================================================
    
    def run(self) -> None:
        """Main application loop."""
        try:
            if not self.initialize():
                self.console.print("\n[yellow]Inizializzazione fallita. Uscita.[/yellow]")
                return
            
            while True:
                choice = self.ui.show_main_menu()
                
                if choice == "0":
                    # Exit
                    if self.has_pending_changes:
                        if not Confirm.ask(
                            "[yellow]Ci sono modifiche non applicate. Uscire comunque?[/yellow]",
                            default=False
                        ):
                            continue
                    break
                
                elif choice == "1":
                    # View port status
                    self.ui.show_port_status()
                
                elif choice == "2":
                    # View mirroring status
                    self.ui.show_mirroring_status()
                
                elif choice == "3":
                    # Configure mirroring
                    self.handle_configure_mirroring()
                
                elif choice == "4":
                    # Generate script
                    self.handle_generate_script()
                
                elif choice == "5":
                    # Apply configuration
                    self.handle_apply_configuration()
                
                elif choice == "6":
                    # Reload configuration
                    if self.is_connected:
                        self.reload_configuration()
                        self.ui.wait_for_enter()
                    else:
                        self.console.print("[yellow]Non connesso. Riconnessione...[/yellow]")
                        if self.connect_to_device():
                            self.ui.wait_for_enter()
            
        except KeyboardInterrupt:
            self.console.print("\n\n[yellow]Interrotto dall'utente[/yellow]")
        
        finally:
            self.disconnect()
            self.console.print("\n[dim]Arrivederci![/dim]\n")
    
    # =========================================================================
    # Configure mirroring
    # =========================================================================
    
    def handle_configure_mirroring(self) -> None:
        """Handle mirroring configuration."""
        if not self.config_loaded:
            self.console.print("[red]Configurazione non caricata[/red]")
            self.ui.wait_for_enter()
            return
        
        result = self.ui.configure_mirroring()
        
        if result:
            destination, sources = result
            self.pending_destination = destination
            self.pending_sources = sources
            self.has_pending_changes = True
            
            self.ui.clear_screen()
            self.ui.print_header("CONFIGURAZIONE COMPLETATA")
            
            # Show commands
            commands = self.ui.generate_mirroring_commands(destination, sources)
            self.ui.show_command_preview(destination, sources)
            
            self.console.print()
            self.console.print(Panel(
                "[bold green]Configurazione salvata in memoria[/bold green]\n\n"
                "Usa le opzioni del menu per:\n"
                "  [4] Genera Script - Crea script riutilizzabile\n"
                "  [5] Applica Configurazione - Applica ora al device",
                box=box.ROUNDED
            ))
            
            self.ui.wait_for_enter()
    
    # =========================================================================
    # Generate script
    # =========================================================================
    
    def handle_generate_script(self) -> None:
        """Handle script generation."""
        self.ui.clear_screen()
        self.ui.print_header("GENERA SCRIPT DI CONFIGURAZIONE")
        
        # Check if we have pending changes or current config
        if self.has_pending_changes:
            destination = self.pending_destination
            sources = self.pending_sources
            self.console.print("[cyan]Usando configurazione in memoria (modifiche pending)[/cyan]\n")
        elif self.config_loaded:
            destination = self.parser.get_mirroring_destination()
            sources = self.parser.get_mirroring_sources()
            if not destination:
                self.console.print("[yellow]Nessun mirroring configurato sul device.[/yellow]")
                self.console.print("Usa prima [3] Configura Port Mirroring.\n")
                self.ui.wait_for_enter()
                return
            self.console.print("[cyan]Usando configurazione attuale del device[/cyan]\n")
        else:
            self.console.print("[red]Nessuna configurazione disponibile[/red]")
            self.ui.wait_for_enter()
            return
        
        # Generate commands
        commands = self.ui.generate_mirroring_commands(destination, sources)
        
        # Show preview
        self.ui.show_command_preview(destination, sources)
        self.console.print()
        
        if not Confirm.ask("Generare gli script?", default=True):
            return
        
        # Generate all formats
        try:
            description = f"Mirroring: {destination} <- {len(sources)} sources"
            
            paths = self.script_gen.generate_all(
                commands=commands,
                device_ip=self.ssh_manager.hostname,
                username=self.ssh_manager.username,
                port=self.ssh_manager.port,
                config=self.parser.config if self.config_loaded else None,
                description=description
            )
            
            self.console.print()
            self.console.print(Panel(
                "[bold green]Script generati con successo![/bold green]\n\n"
                f"[bold]Bash script:[/bold]\n  {paths['bash']}\n\n"
                f"[bold]Python script:[/bold]\n  {paths['python']}\n\n"
                f"[bold]File comandi:[/bold]\n  {paths['commands']}",
                title="FILE GENERATI",
                box=box.ROUNDED
            ))
            
            self.console.print()
            self.console.print("[dim]Per eseguire lo script bash:[/dim]")
            self.console.print(f"  [bold]chmod +x {paths['bash'].name}[/bold]")
            self.console.print(f"  [bold]./{paths['bash'].name}[/bold]")
            
        except Exception as e:
            self.console.print(f"[red]Errore durante la generazione: {e}[/red]")
        
        self.ui.wait_for_enter()
    
    # =========================================================================
    # Apply configuration
    # =========================================================================
    
    def handle_apply_configuration(self) -> None:
        """Handle applying configuration to device."""
        self.ui.clear_screen()
        self.ui.print_header("APPLICA CONFIGURAZIONE")
        
        if not self.is_connected:
            self.console.print("[red]Non connesso al dispositivo[/red]")
            if Confirm.ask("Vuoi riconnetterti?", default=True):
                if not self.connect_to_device():
                    self.ui.wait_for_enter()
                    return
            else:
                self.ui.wait_for_enter()
                return
        
        # Check if we have pending changes
        if not self.has_pending_changes:
            self.console.print("[yellow]Nessuna modifica in sospeso.[/yellow]")
            self.console.print("Usa prima [3] Configura Port Mirroring.\n")
            self.ui.wait_for_enter()
            return
        
        destination = self.pending_destination
        sources = self.pending_sources
        
        # Generate and show commands
        commands = self.ui.generate_mirroring_commands(destination, sources)
        
        self.console.print("[bold]Configurazione da applicare:[/bold]\n")
        self.ui.show_command_preview(destination, sources)
        
        self.console.print()
        self.console.print(Panel(
            "[bold yellow]ATTENZIONE[/bold yellow]\n\n"
            "Questa operazione modificherà la configurazione del port mirroring.\n"
            "Le modifiche saranno attive immediatamente ma potrebbero essere\n"
            "sovrascritte dal controller UniFi al prossimo provisioning.",
            box=box.ROUNDED,
            style="yellow"
        ))
        
        self.console.print()
        if not Confirm.ask("[bold]Applicare la configurazione?[/bold]", default=False):
            self.console.print("[dim]Operazione annullata[/dim]")
            self.ui.wait_for_enter()
            return
        
        # Apply configuration
        self.console.print()
        self.console.print("[dim]Applicazione in corso...[/dim]")
        
        try:
            success, output = self.ssh_manager.apply_mirroring_config(commands)
            
            if success:
                self.console.print()
                self.console.print(Panel(
                    "[bold green]Configurazione applicata con successo![/bold green]",
                    box=box.DOUBLE,
                    style="green"
                ))
                
                # Clear pending changes
                self.has_pending_changes = False
                self.pending_destination = None
                self.pending_sources = []
                
                # Offer to reload
                self.console.print()
                if Confirm.ask("Ricaricare la configurazione per verificare?", default=True):
                    self.reload_configuration()
                
            else:
                self.console.print()
                self.console.print(Panel(
                    f"[bold red]Errore durante l'applicazione[/bold red]\n\n{output}",
                    box=box.ROUNDED,
                    style="red"
                ))
        
        except Exception as e:
            self.console.print(f"[red]Errore: {e}[/red]")
        
        self.ui.wait_for_enter()


# =============================================================================
# Entry point
# =============================================================================

def main():
    """Application entry point."""
    app = PortMirroringManager()
    app.run()


if __name__ == "__main__":
    main()
