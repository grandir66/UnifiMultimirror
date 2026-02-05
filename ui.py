#!/usr/bin/env python3
"""
Text-based User Interface for Ubiquiti Port Mirroring Manager.
Uses the 'rich' library for enhanced terminal output.
"""

import os
import sys
from typing import Optional, List, Set, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.style import Style
from rich import box

from config_parser import ConfigParser, SwitchConfig, InterfaceConfig, LAGConfig


class PortMirroringUI:
    """Text-based UI for Port Mirroring configuration."""
    
    def __init__(self):
        self.console = Console()
        self.config: Optional[SwitchConfig] = None
        self.parser: Optional[ConfigParser] = None
        
        # Current mirroring selection
        self.selected_destination: Optional[str] = None
        self.selected_sources: Set[str] = set()
        
        # Device info
        self.device_ip: str = ""
        self.device_user: str = ""
    
    def set_config(self, parser: ConfigParser) -> None:
        """Set the configuration parser."""
        self.parser = parser
        self.config = parser.config
        
        # Load current mirroring state
        self.selected_destination = parser.get_mirroring_destination()
        self.selected_sources = set(parser.get_mirroring_sources())
    
    def set_device_info(self, ip: str, user: str) -> None:
        """Set device connection info for display."""
        self.device_ip = ip
        self.device_user = user
    
    def _get_port_sort_key(self, port_id: str) -> Tuple[int, int]:
        """Get sort key for port ID (prefix, number)."""
        if "/" in port_id:
            parts = port_id.split("/")
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                return (999, 0)
        return (999, 0)
    
    # =========================================================================
    # Screen utilities
    # =========================================================================
    
    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def wait_for_enter(self, message: str = "Premi INVIO per continuare...") -> None:
        """Wait for user to press Enter."""
        self.console.print(f"\n[dim]{message}[/dim]")
        input()
    
    def print_header(self, title: str = "UBIQUITI PORT MIRRORING MANAGER") -> None:
        """Print application header."""
        self.clear_screen()
        
        # Build header text
        header_lines = [title]
        
        if self.config and self.config.system_info.hostname:
            header_lines.append(f"Device: {self.config.system_info.hostname}")
        elif self.device_ip:
            header_lines.append(f"Device: {self.device_ip}")
        
        if self.config and self.config.system_info.description:
            # Extract model from description
            desc = self.config.system_info.description
            if "," in desc:
                model = desc.split(",")[0]
                header_lines.append(f"Model: {model}")
        
        header_text = "\n".join(header_lines)
        
        self.console.print(Panel(
            header_text,
            style="bold white on blue",
            box=box.DOUBLE
        ))
        self.console.print()
    
    # =========================================================================
    # Main menu
    # =========================================================================
    
    def show_main_menu(self) -> str:
        """Display main menu and return selected option."""
        self.print_header()
        
        menu_items = [
            ("1", "Visualizza Stato Porte"),
            ("2", "Visualizza Configurazione Mirroring"),
            ("3", "Configura Port Mirroring"),
            ("4", "Genera Script di Configurazione"),
            ("5", "Applica Configurazione al Device"),
            ("6", "Ricarica Configurazione dal Device"),
            ("0", "Esci"),
        ]
        
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        table.add_column("Opzione", style="bold cyan")
        table.add_column("Descrizione")
        
        for opt, desc in menu_items:
            table.add_row(f"[{opt}]", desc)
        
        self.console.print(table)
        self.console.print()
        
        choice = Prompt.ask(
            "Seleziona opzione",
            choices=["0", "1", "2", "3", "4", "5", "6"],
            default="1"
        )
        
        return choice
    
    # =========================================================================
    # Port status view
    # =========================================================================
    
    def show_port_status(self) -> None:
        """Display port status with menu for full/compact view."""
        while True:
            self.print_header("STATO PORTE SWITCH")
            
            if not self.config:
                self.console.print("[red]Configurazione non caricata[/red]")
                self.wait_for_enter()
                return
            
            # Show options
            self.console.print("[bold]Opzioni visualizzazione:[/bold]")
            self.console.print("  [1] Vista completa (tutte le porte)")
            self.console.print("  [2] Vista compatta (solo porte UP e in mirroring)")
            self.console.print("  [0] Torna al menu principale")
            self.console.print()
            
            choice = Prompt.ask("Seleziona", choices=["0", "1", "2"], default="1")
            
            if choice == "0":
                return
            elif choice == "1":
                self._show_ports_full()
            elif choice == "2":
                self._show_ports_compact()
    
    def _show_ports_full(self) -> None:
        """Display full port status table with all ports."""
        self.clear_screen()
        self.print_header("STATO PORTE - VISTA COMPLETA")
        
        self._render_port_table(compact=False)
        
        # LAG table
        if self.config.lags:
            self.console.print()
            self._show_lag_table()
        
        self.wait_for_enter()
    
    def _show_ports_compact(self) -> None:
        """Display compact view with only UP ports and mirroring ports."""
        self.clear_screen()
        self.print_header("STATO PORTE - VISTA COMPATTA")
        
        self._render_port_table(compact=True)
        
        # LAG table (only active)
        if self.config.lags:
            active_lags = {k: v for k, v in self.config.lags.items() 
                          if v.link_state == "Up" or self.parser.is_mirroring_source(k)}
            if active_lags:
                self.console.print()
                self._show_lag_table(only_active=True)
        
        self.wait_for_enter()
    
    def _render_port_table(self, compact: bool = False) -> None:
        """Render the port status table."""
        if not self.config or not self.parser:
            return
        
        # Create table
        table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
        
        table.add_column("Porta", style="bold", width=6, justify="center")
        table.add_column("Descrizione", width=26)
        table.add_column("Stato", width=5, justify="center")
        table.add_column("PVID", width=5, justify="center")
        table.add_column("Tagged VLANs", width=22)
        table.add_column("Mirroring", width=16)
        
        # Get sorted physical ports
        ports = self.parser.get_physical_ports()
        
        dest_port = self.parser.get_mirroring_destination()
        source_ports = set(self.parser.get_mirroring_sources())
        
        for port_id in ports:
            iface = self.config.interfaces.get(port_id)
            if not iface:
                continue
            
            is_up = iface.link_state == "Up"
            is_dest = port_id == dest_port
            is_source = port_id in source_ports
            
            # Compact mode: skip ports that are DOWN and not in mirroring
            if compact and not is_up and not is_dest and not is_source:
                continue
            
            # State styling
            if is_up:
                state_text = Text("UP", style="bold green")
            else:
                state_text = Text("DOWN", style="dim")
            
            # VLAN PVID
            pvid_text = str(iface.pvid)
            
            # Tagged VLANs - format as compact string
            tagged_vlans = ConfigParser.format_vlan_list(iface.tagged_vlans)
            if len(tagged_vlans) > 22:
                tagged_vlans = tagged_vlans[:19] + "..."
            if not tagged_vlans:
                tagged_vlans = "-"
            
            # Mirroring status with clear visual
            if is_dest:
                mirror_text = Text("◀◀ DEST", style="bold magenta on black")
            elif is_source:
                mirror_text = Text("▶▶ SRC", style="bold cyan")
            else:
                mirror_text = Text("-", style="dim")
            
            # Row style based on mirroring
            row_style = ""
            if is_dest:
                row_style = "on dark_magenta"
            elif is_source:
                row_style = ""
            
            table.add_row(
                port_id,
                (iface.description or "")[:26],
                state_text,
                pvid_text,
                tagged_vlans,
                mirror_text,
                style=row_style
            )
        
        self.console.print(table)
        
        # Summary
        self.console.print()
        self._show_mirroring_summary()
    
    def _show_mirroring_summary(self) -> None:
        """Show a clear mirroring summary box."""
        if not self.parser:
            return
        
        dest = self.parser.get_mirroring_destination()
        sources = self.parser.get_mirroring_sources()
        
        if not dest:
            self.console.print(Panel(
                "[yellow]Nessun port mirroring configurato[/yellow]",
                title="MIRRORING",
                box=box.ROUNDED,
                width=60
            ))
            return
        
        # Build summary
        dest_iface = self.config.interfaces.get(dest) if self.config else None
        dest_desc = dest_iface.description if dest_iface else ""
        
        lines = [
            f"[bold magenta]DESTINATION:[/bold magenta] {dest}" + 
            (f" ({dest_desc})" if dest_desc else ""),
            "",
            f"[bold cyan]SOURCES ({len(sources)}):[/bold cyan]"
        ]
        
        # Group sources for display
        source_list = sorted(sources, key=self._get_port_sort_key)
        
        # Show in columns (4 per row)
        row = []
        for src in source_list:
            row.append(src)
            if len(row) == 6:
                lines.append("  " + "  ".join(row))
                row = []
        if row:
            lines.append("  " + "  ".join(row))
        
        self.console.print(Panel(
            "\n".join(lines),
            title="MIRRORING ATTIVO",
            box=box.DOUBLE,
            width=60,
            style="bold"
        ))
    
    def _show_lag_table(self, only_active: bool = False) -> None:
        """Display LAG status table."""
        if not self.config or not self.config.lags:
            return
        
        table = Table(
            title="Link Aggregation Groups (LAG)",
            box=box.ROUNDED,
            show_lines=False
        )
        
        table.add_column("LAG", style="bold", width=6)
        table.add_column("Nome", width=6)
        table.add_column("Stato", width=5, justify="center")
        table.add_column("Porte Membri", width=14)
        table.add_column("PVID", width=4, justify="center")
        table.add_column("Tagged", width=18)
        table.add_column("Mirroring", width=12)
        
        for lag_id in sorted(self.config.lags.keys(), key=lambda x: int(x.split("/")[1])):
            lag = self.config.lags[lag_id]
            
            is_up = lag.link_state == "Up"
            is_source = self.parser.is_mirroring_source(lag_id) if self.parser else False
            
            # Filter based on mode
            if only_active and not is_up and not is_source:
                continue
            if not only_active and not lag.member_ports and not is_up:
                continue
            
            # State styling
            if is_up:
                state_text = Text("UP", style="bold green")
            else:
                state_text = Text("DOWN", style="dim")
            
            # Mirroring status
            if is_source:
                mirror_text = Text("▶▶ SRC", style="bold cyan")
            else:
                mirror_text = Text("-", style="dim")
            
            # Get VLAN from LAG interface config
            lag_iface = self.config.interfaces.get(f"lag{lag_id.split('/')[1]}")
            if lag_iface:
                pvid = str(lag_iface.pvid)
                tagged = ConfigParser.format_vlan_list(lag_iface.tagged_vlans)
                if len(tagged) > 18:
                    tagged = tagged[:15] + "..."
                if not tagged:
                    tagged = "-"
            else:
                pvid = "1"
                tagged = "-"
            
            table.add_row(
                lag_id,
                lag.name,
                state_text,
                ",".join(lag.member_ports) or "-",
                pvid,
                tagged,
                mirror_text
            )
        
        self.console.print(table)
    
    # =========================================================================
    # Mirroring status view
    # =========================================================================
    
    def show_mirroring_status(self) -> None:
        """Display current mirroring configuration in a clear format."""
        self.print_header("CONFIGURAZIONE MIRRORING ATTUALE")
        
        if not self.config:
            self.console.print("[red]Configurazione non caricata[/red]")
            self.wait_for_enter()
            return
        
        if not self.config.monitor_sessions:
            self.console.print(Panel(
                "[yellow]Nessuna sessione di mirroring configurata[/yellow]",
                title="Monitor Session",
                box=box.ROUNDED
            ))
            self.wait_for_enter()
            return
        
        for session_id, session in self.config.monitor_sessions.items():
            # ===== DESTINATION BOX =====
            if session.destination:
                dest_iface = self.config.interfaces.get(session.destination)
                dest_desc = dest_iface.description if dest_iface else ""
                dest_state = ""
                if dest_iface:
                    dest_state = "[green]UP[/green]" if dest_iface.link_state == "Up" else "[dim]DOWN[/dim]"
                
                dest_content = f"[bold]{session.destination}[/bold] {dest_state}\n{dest_desc}"
                
                self.console.print(Panel(
                    dest_content,
                    title="◀◀ DESTINATION (porta di monitoraggio)",
                    box=box.DOUBLE,
                    style="magenta",
                    width=60
                ))
            else:
                self.console.print(Panel(
                    "[yellow]Non configurata[/yellow]",
                    title="DESTINATION",
                    box=box.ROUNDED,
                    width=60
                ))
            
            self.console.print()
            
            # ===== SOURCES TABLE =====
            if session.sources:
                table = Table(
                    title=f"▶▶ SOURCE PORTS ({len(session.sources)} porte monitorate)",
                    box=box.ROUNDED,
                    show_lines=False,
                    width=60
                )
                
                table.add_column("Porta", style="bold cyan", width=8)
                table.add_column("Stato", width=6, justify="center")
                table.add_column("Descrizione", width=36)
                
                # Sort sources
                sources_sorted = sorted(session.sources, key=self._get_port_sort_key)
                
                for src in sources_sorted:
                    src_iface = self.config.interfaces.get(src)
                    
                    if src_iface:
                        state = Text("UP", style="green") if src_iface.link_state == "Up" else Text("DOWN", style="dim")
                        desc = src_iface.description or ""
                    else:
                        # Check if it's a LAG
                        lag = self.config.lags.get(src)
                        if lag:
                            state = Text("UP", style="green") if lag.link_state == "Up" else Text("DOWN", style="dim")
                            desc = f"LAG {lag.name} ({','.join(lag.member_ports)})"
                        else:
                            state = Text("-", style="dim")
                            desc = ""
                    
                    table.add_row(src, state, desc[:36])
                
                self.console.print(table)
            else:
                self.console.print("[yellow]Nessuna porta source configurata[/yellow]")
        
        self.wait_for_enter()
    
    # =========================================================================
    # Mirroring configuration with checkbox style
    # =========================================================================
    
    def configure_mirroring(self) -> Optional[Tuple[str, List[str]]]:
        """
        Interactive mirroring configuration with checkbox-style selection.
        Returns (destination, sources) or None if cancelled.
        """
        if not self.config or not self.parser:
            self.console.print("[red]Configurazione non caricata[/red]")
            self.wait_for_enter()
            return None
        
        # Initialize with current config
        current_dest = self.parser.get_mirroring_destination()
        current_sources = set(self.parser.get_mirroring_sources())
        
        selected_dest = current_dest
        selected_sources = current_sources.copy()
        
        # Get all available ports
        all_ports = self._get_all_available_ports()
        
        while True:
            self.clear_screen()
            self.print_header("CONFIGURA PORT MIRRORING")
            
            # ===== DESTINATION SECTION =====
            self.console.print("[bold]STEP 1: PORTA DESTINATION[/bold] (riceve il traffico mirrorato)")
            self.console.print()
            
            if selected_dest:
                dest_iface = self.config.interfaces.get(selected_dest)
                dest_desc = dest_iface.description if dest_iface else ""
                self.console.print(Panel(
                    f"[bold magenta]{selected_dest}[/bold magenta] - {dest_desc}",
                    title="◀◀ DESTINATION SELEZIONATA",
                    box=box.ROUNDED,
                    width=60
                ))
            else:
                self.console.print(Panel(
                    "[yellow]Nessuna destination selezionata[/yellow]",
                    title="DESTINATION",
                    box=box.ROUNDED,
                    width=60
                ))
            
            self.console.print()
            
            # ===== SOURCES SECTION with checkboxes =====
            self.console.print("[bold]STEP 2: PORTE SOURCE[/bold] (traffico da monitorare)")
            self.console.print("[dim]Seleziona/deseleziona inserendo il numero della porta[/dim]")
            self.console.print()
            
            # Create checkbox table
            self._show_checkbox_table(all_ports, selected_dest, selected_sources)
            
            self.console.print()
            
            # ===== MENU OPTIONS =====
            self.console.print("[bold]Comandi:[/bold]")
            self.console.print("  [D] Cambia DESTINATION")
            self.console.print("  [numero] Toggle porta source (es: 4 per 0/4)")
            self.console.print("  [A] Seleziona TUTTE le porte come source")
            self.console.print("  [N] Deseleziona tutte le porte source")
            self.console.print("  [R] Range porte (es: 17-24)")
            self.console.print("  [C] CONFERMA e salva")
            self.console.print("  [X] Annulla ed esci")
            self.console.print()
            
            choice = Prompt.ask("Comando").strip().upper()
            
            if choice == "X":
                return None
            
            elif choice == "C":
                # Confirm
                if not selected_dest:
                    self.console.print("[red]Devi selezionare una porta DESTINATION[/red]")
                    self.wait_for_enter()
                    continue
                
                if not selected_sources:
                    self.console.print("[red]Devi selezionare almeno una porta SOURCE[/red]")
                    self.wait_for_enter()
                    continue
                
                # Show confirmation
                return self._show_config_confirmation(selected_dest, list(selected_sources))
            
            elif choice == "D":
                # Change destination
                new_dest = self._select_destination(all_ports, selected_dest)
                if new_dest:
                    # Remove from sources if was selected
                    selected_sources.discard(new_dest)
                    selected_dest = new_dest
            
            elif choice == "A":
                # Select all
                for port_id, _, _ in all_ports:
                    if port_id != selected_dest:
                        selected_sources.add(port_id)
            
            elif choice == "N":
                # Deselect all
                selected_sources.clear()
            
            elif choice == "R":
                # Range input
                range_str = Prompt.ask("Inserisci range (es: 17-24 o 0/17-0/24)")
                ports_in_range = self._parse_port_range(range_str)
                for p in ports_in_range:
                    if p != selected_dest and p in {x[0] for x in all_ports}:
                        selected_sources.add(p)
            
            else:
                # Try to parse as port number for toggle
                port_id = self._normalize_port_id(choice)
                if port_id and port_id in {p[0] for p in all_ports}:
                    if port_id == selected_dest:
                        self.console.print("[yellow]Non puoi selezionare la destination come source[/yellow]")
                        self.wait_for_enter()
                    elif port_id in selected_sources:
                        selected_sources.remove(port_id)
                    else:
                        selected_sources.add(port_id)
    
    def _get_all_available_ports(self) -> List[Tuple[str, str, str]]:
        """Get all available ports for selection."""
        ports = []
        
        # Physical ports
        for port_id in self.parser.get_physical_ports():
            iface = self.config.interfaces.get(port_id)
            if iface:
                ports.append((port_id, iface.description or "", iface.link_state))
        
        # LAG ports
        for lag_id in self.parser.get_lag_ports():
            lag = self.config.lags.get(lag_id)
            if lag and (lag.member_ports or lag.link_state == "Up"):
                desc = f"LAG {lag.name} ({','.join(lag.member_ports)})"
                ports.append((lag_id, desc, lag.link_state))
        
        return ports
    
    def _show_checkbox_table(
        self, 
        ports: List[Tuple[str, str, str]], 
        dest: Optional[str],
        sources: Set[str]
    ) -> None:
        """Show ports with checkbox-style selection."""
        table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
        
        table.add_column("", width=3, justify="center")  # Checkbox
        table.add_column("Porta", style="bold", width=6)
        table.add_column("Descrizione", width=24)
        table.add_column("Stato", width=5, justify="center")
        table.add_column("PVID", width=4, justify="center")
        table.add_column("Tagged", width=18)
        table.add_column("Ruolo", width=12)
        
        for port_id, desc, state in ports:
            # Checkbox
            if port_id == dest:
                checkbox = Text("◀◀", style="bold magenta")
                role = Text("DESTINATION", style="bold magenta")
                row_style = "on dark_magenta"
            elif port_id in sources:
                checkbox = Text("[X]", style="bold cyan")
                role = Text("SOURCE", style="cyan")
                row_style = ""
            else:
                checkbox = Text("[ ]", style="dim")
                role = Text("-", style="dim")
                row_style = "dim" if state == "Down" else ""
            
            # State
            state_text = Text("UP", style="green") if state == "Up" else Text("DOWN", style="dim")
            
            # VLAN info
            iface = self.config.interfaces.get(port_id)
            if iface:
                pvid = str(iface.pvid)
                tagged = ConfigParser.format_vlan_list(iface.tagged_vlans)
                if len(tagged) > 18:
                    tagged = tagged[:15] + "..."
                if not tagged:
                    tagged = "-"
            else:
                pvid = "1"
                tagged = "-"
            
            table.add_row(
                checkbox,
                port_id,
                desc[:24],
                state_text,
                pvid,
                tagged,
                role,
                style=row_style
            )
        
        self.console.print(table)
        
        # Stats
        self.console.print()
        self.console.print(f"[dim]Porte source selezionate: [bold]{len(sources)}[/bold][/dim]")
    
    def _select_destination(
        self, 
        ports: List[Tuple[str, str, str]], 
        current: Optional[str]
    ) -> Optional[str]:
        """Select destination port."""
        self.clear_screen()
        self.print_header("SELEZIONA DESTINATION")
        
        self.console.print("Seleziona la porta che riceverà il traffico mirrorato:")
        self.console.print()
        
        table = Table(box=box.ROUNDED, show_lines=False)
        table.add_column("Porta", style="bold", width=8)
        table.add_column("Descrizione", width=32)
        table.add_column("Stato", width=6)
        
        for port_id, desc, state in ports:
            style = "bold magenta" if port_id == current else ""
            state_text = "UP" if state == "Up" else "DOWN"
            state_style = "green" if state == "Up" else "dim"
            
            table.add_row(
                Text(port_id, style=style),
                Text(desc[:32], style=style),
                Text(state_text, style=state_style)
            )
        
        self.console.print(table)
        self.console.print()
        
        choice = Prompt.ask(
            "Inserisci porta (es: 0/3) o X per annullare",
            default=current or ""
        )
        
        if choice.upper() == "X":
            return None
        
        port_id = self._normalize_port_id(choice)
        if port_id and port_id in {p[0] for p in ports}:
            return port_id
        
        self.console.print(f"[red]Porta non valida: {choice}[/red]")
        self.wait_for_enter()
        return current
    
    def _show_config_confirmation(
        self, 
        dest: str, 
        sources: List[str]
    ) -> Optional[Tuple[str, List[str]]]:
        """Show configuration confirmation screen."""
        self.clear_screen()
        self.print_header("CONFERMA CONFIGURAZIONE")
        
        # Destination box
        dest_iface = self.config.interfaces.get(dest)
        dest_desc = dest_iface.description if dest_iface else ""
        
        self.console.print(Panel(
            f"[bold]{dest}[/bold]\n{dest_desc}",
            title="◀◀ DESTINATION",
            box=box.DOUBLE,
            style="magenta",
            width=50
        ))
        
        self.console.print()
        
        # Sources table
        table = Table(
            title=f"▶▶ SOURCE PORTS ({len(sources)})",
            box=box.ROUNDED,
            width=50
        )
        table.add_column("Porta", style="cyan", width=8)
        table.add_column("Descrizione", width=32)
        
        sources_sorted = sorted(sources, key=self._get_port_sort_key)
        for src in sources_sorted:
            src_iface = self.config.interfaces.get(src)
            desc = src_iface.description if src_iface else ""
            if not desc and src.startswith("3/"):
                lag = self.config.lags.get(src)
                if lag:
                    desc = f"LAG {lag.name}"
            table.add_row(src, desc[:32])
        
        self.console.print(table)
        
        self.console.print()
        
        # Commands preview
        commands = self.generate_mirroring_commands(dest, sources)
        self.console.print(Panel(
            "\n".join(commands),
            title="COMANDI DA ESEGUIRE",
            box=box.ROUNDED,
            style="dim"
        ))
        
        self.console.print()
        
        if Confirm.ask("[bold]Confermare questa configurazione?[/bold]", default=True):
            self.selected_destination = dest
            self.selected_sources = set(sources)
            return (dest, sources)
        
        return None
    
    def _normalize_port_id(self, port_str: str) -> Optional[str]:
        """Normalize port ID input."""
        port_str = port_str.strip()
        
        # Handle formats: 0/3, 03, 3 (for physical), 3/1 (for LAG)
        if "/" in port_str:
            return port_str
        
        # Try to parse as number for physical port
        try:
            num = int(port_str)
            return f"0/{num}"
        except ValueError:
            return None
    
    def _parse_port_range(self, range_str: str) -> List[str]:
        """
        Parse port range string like "0/4,0/8,0/17-0/24,3/1".
        Returns list of port IDs.
        """
        ports = []
        
        if not range_str:
            return ports
        
        parts = range_str.replace(" ", "").split(",")
        
        for part in parts:
            if "-" in part:
                # Range: 0/17-0/24 or 17-24
                try:
                    start_str, end_str = part.split("-", 1)
                    
                    # Parse start
                    if "/" in start_str:
                        prefix, start_num = start_str.rsplit("/", 1)
                        start = int(start_num)
                    else:
                        prefix = "0"
                        start = int(start_str)
                    
                    # Parse end
                    if "/" in end_str:
                        _, end_num = end_str.rsplit("/", 1)
                        end = int(end_num)
                    else:
                        end = int(end_str)
                    
                    for i in range(start, end + 1):
                        ports.append(f"{prefix}/{i}")
                        
                except ValueError:
                    continue
            else:
                # Single port
                normalized = self._normalize_port_id(part)
                if normalized:
                    ports.append(normalized)
        
        return ports
    
    # =========================================================================
    # Command preview
    # =========================================================================
    
    def show_command_preview(self, destination: str, sources: List[str], session_id: int = 1) -> List[str]:
        """Show preview of commands to be executed."""
        commands = self.generate_mirroring_commands(destination, sources, session_id)
        
        self.console.print(Panel(
            "\n".join(commands),
            title="COMANDI DA ESEGUIRE",
            box=box.ROUNDED,
            style="dim"
        ))
        
        return commands
    
    def generate_mirroring_commands(
        self, 
        destination: str, 
        sources: List[str], 
        session_id: int = 1
    ) -> List[str]:
        """Generate list of mirroring configuration commands."""
        commands = []
        
        # Clear existing session
        commands.append(f"no monitor session {session_id}")
        
        # Set destination
        commands.append(f"monitor session {session_id} destination interface {destination}")
        
        # Add sources
        for src in sorted(sources, key=lambda x: (
            0 if x.startswith("0/") else 1,
            int(x.split("/")[1]) if "/" in x else 0
        )):
            commands.append(f"monitor session {session_id} source interface {src}")
        
        # Enable session
        commands.append(f"monitor session {session_id} mode")
        
        return commands


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    ui = PortMirroringUI()
    
    # Test with mock data
    from config_parser import ConfigParser
    
    sample_config = """
!System Description "USW-Pro-Aggregation, 7.1.26.15869"
snmp-server sysname "SW-CED-AGG-243"
network parms 192.168.40.243 255.255.255.0 192.168.40.254

interface 0/1
description 'SFP_ 1'
exit

interface 0/2
description 'SFP_ 2'
exit

interface 0/3
description 'SFP_ 3 - MONITORING PORT'
exit

interface 0/4
description 'SFP_ 4 - SW CED 237'
exit

monitor session 1 destination interface 0/3
monitor session 1 source interface 0/4
monitor session 1 mode
"""
    
    sample_status = """
Port       Name                          State   Mode        Status      Type
---------  ----------------------------  ------  ----------  ----------  ------------------
0/1        SFP_ 1                        Down    Auto D                  Unknown
0/2        SFP_ 2                        Down    10G Full                Unknown
0/3        SFP_ 3 - MONITORING PORT      Up      Auto D      10G Full    DAC
0/4        SFP_ 4 - SW CED 237           Up      10G Full    10G Full    DAC
"""
    
    parser = ConfigParser()
    parser.parse_running_config(sample_config)
    parser.parse_interfaces_status(sample_status)
    
    ui.set_config(parser)
    ui.set_device_info("192.168.40.243", "admin")
    
    # Show menu
    choice = ui.show_main_menu()
    print(f"Selected: {choice}")
