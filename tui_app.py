#!/usr/bin/env python3
"""
Textual-based TUI Application for Ubiquiti Port Mirroring Manager.
Full-screen application with keyboard navigation and interactive selection.
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Button, Label, Input, 
    DataTable, TabbedContent, TabPane, Checkbox, Rule
)
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual.message import Message
from textual import work
from textual import events
from rich.text import Text

from typing import Optional, List, Set, Tuple
from pathlib import Path

from ssh_manager import SSHManager
from config_parser import ConfigParser, SwitchConfig


# =============================================================================
# Login Screen
# =============================================================================

class LoginScreen(ModalScreen):
    """Modal screen for SSH login."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Annulla"),
    ]
    
    CSS = """
    LoginScreen {
        align: center middle;
    }
    
    #login-container {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    
    #login-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    
    .login-label {
        margin-top: 1;
    }
    
    .login-input {
        margin-bottom: 1;
    }
    
    #login-buttons {
        margin-top: 1;
        align: center middle;
    }
    
    #login-buttons Button {
        margin: 0 1;
    }
    
    #login-error {
        color: $error;
        text-align: center;
        margin-top: 1;
    }
    """
    
    def __init__(self, saved_ip: str = ""):
        super().__init__()
        self.saved_ip = saved_ip
        self.result: Optional[Tuple[str, str]] = None
    
    def compose(self) -> ComposeResult:
        with Container(id="login-container"):
            yield Label("CONNESSIONE AL DISPOSITIVO", id="login-title")
            yield Rule()
            yield Label("IP del dispositivo:", classes="login-label")
            yield Input(value=self.saved_ip, placeholder="192.168.1.1", id="ip-input", classes="login-input")
            yield Label("Password (utente: admin):", classes="login-label")
            yield Input(placeholder="password", password=True, id="password-input", classes="login-input")
            yield Label("", id="login-error")
            with Horizontal(id="login-buttons"):
                yield Button("Connetti", variant="primary", id="btn-connect")
                yield Button("Esci", variant="default", id="btn-cancel")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-connect":
            ip = self.query_one("#ip-input", Input).value.strip()
            password = self.query_one("#password-input", Input).value
            
            if not ip:
                self.query_one("#login-error", Label).update("IP non valido")
                return
            if not password:
                self.query_one("#login-error", Label).update("Password non valida")
                return
            
            self.result = (ip, password)
            self.dismiss(self.result)
        
        elif event.button.id == "btn-cancel":
            self.dismiss(None)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Press Enter to submit
        if event.input.id == "password-input":
            self.query_one("#btn-connect", Button).press()
        elif event.input.id == "ip-input":
            self.query_one("#password-input", Input).focus()
    
    def action_cancel(self) -> None:
        self.dismiss(None)


# =============================================================================
# Port Selection Screen (for mirroring configuration)
# =============================================================================

class PortSelectionScreen(Screen):
    """Full-screen port selection with keyboard navigation."""
    
    BINDINGS = [
        Binding("up", "move_up", "Su"),
        Binding("down", "move_down", "Giù"),
        Binding("space", "toggle_select", "Seleziona"),
        Binding("enter", "toggle_select", "Seleziona"),
        Binding("a", "select_all", "Tutti"),
        Binding("n", "select_none", "Nessuno"),
        Binding("d", "set_destination", "Destination"),
        Binding("escape", "cancel", "Annulla"),
        Binding("f10", "confirm", "Conferma"),
    ]
    
    CSS = """
    PortSelectionScreen {
        layout: vertical;
    }
    
    #port-table-container {
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }
    
    #selection-info {
        height: 5;
        border: solid $accent;
        margin: 0 1 1 1;
        padding: 0 1;
    }
    
    #info-destination {
        color: $warning;
    }
    
    #info-sources {
        color: $success;
    }
    
    .highlight-row {
        background: $accent;
    }
    """
    
    def __init__(
        self, 
        ports: List[Tuple[str, str, str, int, str]],  # (id, desc, state, pvid, tagged)
        current_dest: Optional[str],
        current_sources: Set[str]
    ):
        super().__init__()
        self.ports = ports
        self.destination = current_dest
        self.sources = current_sources.copy()
        self.cursor_row = 0
        self.result: Optional[Tuple[str, List[str]]] = None
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="port-table-container"):
            table = DataTable(id="port-table", cursor_type="row")
            yield table
        
        with Container(id="selection-info"):
            yield Label("DESTINATION: (nessuna)", id="info-destination")
            yield Label("SOURCES: 0 porte selezionate", id="info-sources")
            yield Label("[D]=Destination [SPAZIO]=Toggle [A]=Tutti [N]=Nessuno [F10]=Conferma [ESC]=Annulla", id="info-help")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the table."""
        table = self.query_one("#port-table", DataTable)
        
        # Add columns
        table.add_column("", width=3, key="check")
        table.add_column("Porta", width=8, key="port")
        table.add_column("Descrizione", width=28, key="desc")
        table.add_column("Stato", width=6, key="state")
        table.add_column("PVID", width=5, key="pvid")
        table.add_column("Tagged VLANs", width=24, key="tagged")
        table.add_column("Ruolo", width=14, key="role")
        
        # Add rows
        for port_id, desc, state, pvid, tagged in self.ports:
            self._add_port_row(table, port_id, desc, state, pvid, tagged)
        
        # Update info
        self._update_info()
        
        # Focus table
        table.focus()
    
    def _add_port_row(self, table: DataTable, port_id: str, desc: str, state: str, pvid: int, tagged: str) -> None:
        """Add a row to the table."""
        # Checkbox
        if port_id == self.destination:
            check = Text("◀◀", style="bold magenta")
            role = Text("DESTINATION", style="bold magenta")
        elif port_id in self.sources:
            check = Text("[X]", style="bold cyan")
            role = Text("SOURCE", style="bold cyan")
        else:
            check = Text("[ ]", style="dim")
            role = Text("-", style="dim")
        
        # State
        state_text = Text("UP", style="bold green") if state == "Up" else Text("DOWN", style="dim")
        
        table.add_row(
            check,
            port_id,
            desc[:28],
            state_text,
            str(pvid),
            tagged[:24] if tagged else "-",
            role,
            key=port_id
        )
    
    def _refresh_table(self) -> None:
        """Refresh all rows in the table."""
        table = self.query_one("#port-table", DataTable)
        
        for port_id, desc, state, pvid, tagged in self.ports:
            # Checkbox
            if port_id == self.destination:
                check = Text("◀◀", style="bold magenta")
                role = Text("DESTINATION", style="bold magenta")
            elif port_id in self.sources:
                check = Text("[X]", style="bold cyan")
                role = Text("SOURCE", style="bold cyan")
            else:
                check = Text("[ ]", style="dim")
                role = Text("-", style="dim")
            
            state_text = Text("UP", style="bold green") if state == "Up" else Text("DOWN", style="dim")
            
            # Update row
            table.update_cell(port_id, "check", check)
            table.update_cell(port_id, "role", role)
        
        self._update_info()
    
    def _update_info(self) -> None:
        """Update the info panel."""
        dest_label = self.query_one("#info-destination", Label)
        src_label = self.query_one("#info-sources", Label)
        
        if self.destination:
            # Find description
            desc = ""
            for p in self.ports:
                if p[0] == self.destination:
                    desc = p[1]
                    break
            dest_label.update(f"DESTINATION: {self.destination} ({desc})")
        else:
            dest_label.update("DESTINATION: (nessuna - premi D per impostare)")
        
        src_label.update(f"SOURCES: {len(self.sources)} porte selezionate")
    
    def action_move_up(self) -> None:
        table = self.query_one("#port-table", DataTable)
        table.action_cursor_up()
    
    def action_move_down(self) -> None:
        table = self.query_one("#port-table", DataTable)
        table.action_cursor_down()
    
    def action_toggle_select(self) -> None:
        """Toggle selection of current row."""
        table = self.query_one("#port-table", DataTable)
        
        if table.cursor_row is None:
            return
        
        # Get port_id from our ports list using cursor position
        if table.cursor_row >= len(self.ports):
            return
        
        port_id = self.ports[table.cursor_row][0]
        
        if port_id == self.destination:
            # Can't select destination as source
            self.notify("Non puoi selezionare la destination come source", severity="warning")
            return
        
        if port_id in self.sources:
            self.sources.remove(port_id)
        else:
            self.sources.add(port_id)
        
        self._refresh_table()
    
    def action_set_destination(self) -> None:
        """Set current row as destination."""
        table = self.query_one("#port-table", DataTable)
        
        if table.cursor_row is None:
            return
        
        # Get port_id from our ports list using cursor position
        if table.cursor_row >= len(self.ports):
            return
        
        port_id = self.ports[table.cursor_row][0]
        
        # Remove from sources if was selected
        self.sources.discard(port_id)
        self.destination = port_id
        
        self._refresh_table()
        self.notify(f"Destination impostata: {port_id}", severity="information")
    
    def action_select_all(self) -> None:
        """Select all ports as source (except destination)."""
        for port_id, _, _, _, _ in self.ports:
            if port_id != self.destination:
                self.sources.add(port_id)
        self._refresh_table()
    
    def action_select_none(self) -> None:
        """Deselect all sources."""
        self.sources.clear()
        self._refresh_table()
    
    def action_cancel(self) -> None:
        """Cancel and return to main."""
        self.app.pop_screen()
    
    def action_confirm(self) -> None:
        """Confirm selection."""
        if not self.destination:
            self.notify("Devi selezionare una porta DESTINATION (premi D)", severity="error")
            return
        
        if not self.sources:
            self.notify("Devi selezionare almeno una porta SOURCE", severity="error")
            return
        
        self.result = (self.destination, list(self.sources))
        self.dismiss(self.result)


# =============================================================================
# Main Application
# =============================================================================

class PortMirroringApp(App):
    """Main Textual application for Port Mirroring Manager."""
    
    TITLE = "Ubiquiti Port Mirroring Manager"
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main-container {
        height: 1fr;
    }
    
    #status-bar {
        height: 3;
        dock: bottom;
        background: $primary-background;
        padding: 0 1;
    }
    
    #connection-status {
        color: $success;
    }
    
    .port-table {
        height: 1fr;
    }
    
    #tab-ports DataTable {
        height: 1fr;
    }
    
    #tab-mirroring {
        padding: 1;
    }
    
    #mirror-info {
        height: auto;
        border: solid $accent;
        padding: 1;
        margin-bottom: 1;
    }
    
    #mirror-dest {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }
    
    #mirror-sources-title {
        color: $success;
        text-style: bold;
    }
    
    #action-buttons {
        height: auto;
        margin-top: 1;
    }
    
    #action-buttons Button {
        margin: 0 1 0 0;
    }
    
    .info-panel {
        height: auto;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    #device-info {
        height: auto;
        dock: top;
        background: $primary;
        color: $text;
        padding: 0 1;
        text-align: center;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Esci"),
        Binding("r", "reload", "Ricarica"),
        Binding("c", "configure", "Configura"),
        Binding("g", "generate", "Genera Script"),
        Binding("f5", "apply", "Applica"),
    ]
    
    def __init__(self):
        super().__init__()
        self.ssh_manager = SSHManager()
        self.parser = ConfigParser()
        self.is_connected = False
        self.device_ip = ""
        
        # Pending configuration
        self.pending_dest: Optional[str] = None
        self.pending_sources: List[str] = []
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Non connesso", id="device-info")
        
        with TabbedContent(id="main-tabs"):
            with TabPane("Stato Porte", id="tab-ports"):
                yield DataTable(id="ports-table", cursor_type="row")
            
            with TabPane("Mirroring", id="tab-mirroring"):
                with Container(id="mirror-info"):
                    yield Label("DESTINATION: -", id="mirror-dest")
                    yield Label("SOURCE PORTS:", id="mirror-sources-title")
                    yield DataTable(id="sources-table", cursor_type="row")
                
                with Horizontal(id="action-buttons"):
                    yield Button("Configura Mirroring", variant="primary", id="btn-configure")
                    yield Button("Genera Script", variant="default", id="btn-generate")
                    yield Button("Applica al Device", variant="warning", id="btn-apply")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Setup tables
        self._setup_ports_table()
        self._setup_sources_table()
        
        # Show login (use call_later to avoid blocking)
        self.call_later(self._show_login_screen)
    
    def _setup_ports_table(self) -> None:
        """Setup the ports table columns."""
        table = self.query_one("#ports-table", DataTable)
        table.add_column("Porta", width=8, key="port")
        table.add_column("Descrizione", width=28, key="desc")
        table.add_column("Stato", width=6, key="state")
        table.add_column("PVID", width=5, key="pvid")
        table.add_column("Tagged VLANs", width=26, key="tagged")
        table.add_column("Mirroring", width=14, key="mirror")
    
    def _setup_sources_table(self) -> None:
        """Setup the sources table columns."""
        table = self.query_one("#sources-table", DataTable)
        table.add_column("Porta", width=10, key="port")
        table.add_column("Descrizione", width=32, key="desc")
        table.add_column("Stato", width=8, key="state")
    
    def _show_login_screen(self) -> None:
        """Show login screen."""
        saved_ip = ""
        if self.ssh_manager.config_exists():
            success, _ = self.ssh_manager.load_config()
            if success:
                saved_ip = self.ssh_manager.hostname
        
        self.push_screen(LoginScreen(saved_ip), callback=self._on_login_result)
    
    def _on_login_result(self, result: Optional[Tuple[str, str]]) -> None:
        """Handle login result."""
        if result is None:
            self.exit()
            return
        
        ip, password = result
        self._do_connect(ip, password)
    
    @work(exclusive=True, thread=True)
    def _do_connect(self, ip: str, password: str) -> None:
        """Connect to device (runs in worker thread)."""
        self.notify(f"Connessione a {ip}...", severity="information")
        
        # Save and load config
        self.ssh_manager.create_config(ip, "admin", password, 22)
        success, msg = self.ssh_manager.load_config()
        
        if not success:
            self.notify(f"Errore: {msg}", severity="error")
            self.call_from_thread(self._show_login_screen)
            return
        
        # Connect
        success, msg = self.ssh_manager.connect()
        
        if not success:
            self.notify(f"Connessione fallita: {msg}", severity="error")
            self.call_from_thread(self._show_login_screen)
            return
        
        self.is_connected = True
        self.device_ip = ip
        
        # Update header (must be called from main thread)
        self.call_from_thread(self._update_device_info, f"Connesso a {ip} (admin)")
        
        self.notify("Connesso! Caricamento configurazione...", severity="information")
        
        # Load config
        self._load_config_sync()
    
    def _update_device_info(self, text: str) -> None:
        """Update device info label."""
        self.query_one("#device-info", Label).update(text)
    
    def _load_config_sync(self) -> None:
        """Load configuration synchronously (called from worker thread)."""
        if not self.is_connected:
            self.notify("Non connesso", severity="error")
            return
        
        try:
            # Get running config
            running_config = self.ssh_manager.get_running_config()
            self.parser.parse_running_config(running_config)
            
            # Get interface status
            iface_status = self.ssh_manager.get_interfaces_status()
            self.parser.parse_interfaces_status(iface_status)
            
            # Get port-channel
            pc_brief = self.ssh_manager.get_port_channel_brief()
            self.parser.parse_port_channel_brief(pc_brief)
            
            # Update device info
            hostname = self.parser.config.system_info.hostname or self.device_ip
            self.call_from_thread(self._update_device_info, f"{hostname} ({self.device_ip})")
            
            # Refresh tables (must be called from main thread)
            self.call_from_thread(self._refresh_ports_table)
            self.call_from_thread(self._refresh_mirroring_info)
            
            self.notify("Configurazione caricata", severity="information")
            
        except Exception as e:
            self.notify(f"Errore: {e}", severity="error")
    
    @work(exclusive=True, thread=True)
    def _reload_config_worker(self) -> None:
        """Reload configuration in worker thread."""
        self._load_config_sync()
    
    def _refresh_ports_table(self) -> None:
        """Refresh the ports table."""
        table = self.query_one("#ports-table", DataTable)
        table.clear()
        
        dest = self.parser.get_mirroring_destination()
        sources = set(self.parser.get_mirroring_sources())
        
        for port_id in self.parser.get_physical_ports():
            iface = self.parser.config.interfaces.get(port_id)
            if not iface:
                continue
            
            # State
            state = Text("UP", style="bold green") if iface.link_state == "Up" else Text("DOWN", style="dim")
            
            # Tagged VLANs
            tagged = ConfigParser.format_vlan_list(iface.tagged_vlans)
            if len(tagged) > 26:
                tagged = tagged[:23] + "..."
            
            # Mirroring
            if port_id == dest:
                mirror = Text("◀◀ DEST", style="bold magenta")
            elif port_id in sources:
                mirror = Text("▶▶ SRC", style="bold cyan")
            else:
                mirror = Text("-", style="dim")
            
            table.add_row(
                port_id,
                iface.description[:28] if iface.description else "",
                state,
                str(iface.pvid),
                tagged or "-",
                mirror,
                key=port_id
            )
    
    def _refresh_mirroring_info(self) -> None:
        """Refresh mirroring info panel."""
        dest = self.parser.get_mirroring_destination()
        sources = self.parser.get_mirroring_sources()
        
        # Destination
        dest_label = self.query_one("#mirror-dest", Label)
        if dest:
            iface = self.parser.config.interfaces.get(dest)
            desc = iface.description if iface else ""
            dest_label.update(f"DESTINATION: {dest} ({desc})")
        else:
            dest_label.update("DESTINATION: (non configurata)")
        
        # Sources table
        table = self.query_one("#sources-table", DataTable)
        table.clear()
        
        for src in sorted(sources, key=lambda x: (int(x.split("/")[0]), int(x.split("/")[1]))):
            iface = self.parser.config.interfaces.get(src)
            if iface:
                state = "UP" if iface.link_state == "Up" else "DOWN"
                desc = iface.description or ""
            else:
                state = "-"
                desc = ""
            
            table.add_row(src, desc[:32], state, key=src)
        
        # Update title
        self.query_one("#mirror-sources-title", Label).update(f"SOURCE PORTS ({len(sources)}):")
    
    def action_reload(self) -> None:
        """Reload configuration."""
        self._reload_config_worker()
    
    def action_configure(self) -> None:
        """Open port selection screen."""
        if not self.is_connected:
            self.notify("Non connesso", severity="error")
            return
        
        # Prepare port list
        ports = []
        for port_id in self.parser.get_physical_ports():
            iface = self.parser.config.interfaces.get(port_id)
            if iface:
                tagged = ConfigParser.format_vlan_list(iface.tagged_vlans)
                ports.append((port_id, iface.description or "", iface.link_state, iface.pvid, tagged))
        
        # Add LAGs
        for lag_id in self.parser.get_lag_ports():
            lag = self.parser.config.lags.get(lag_id)
            if lag and (lag.member_ports or lag.link_state == "Up"):
                desc = f"LAG {lag.name} ({','.join(lag.member_ports)})"
                ports.append((lag_id, desc, lag.link_state, 1, ""))
        
        current_dest = self.parser.get_mirroring_destination()
        current_sources = set(self.parser.get_mirroring_sources())
        
        # Show selection screen with callback
        self.push_screen(
            PortSelectionScreen(ports, current_dest, current_sources),
            callback=self._on_configure_result
        )
    
    def _on_configure_result(self, result: Optional[Tuple[str, List[str]]]) -> None:
        """Handle configuration result."""
        if result:
            dest, sources = result
            self.pending_dest = dest
            self.pending_sources = sources
            self.notify(f"Configurazione salvata: {dest} <- {len(sources)} sources", severity="information")
    
    def action_generate(self) -> None:
        """Generate configuration script."""
        from script_generator import ScriptGenerator
        
        dest = self.pending_dest or self.parser.get_mirroring_destination()
        sources = self.pending_sources or self.parser.get_mirroring_sources()
        
        if not dest:
            self.notify("Nessuna configurazione da generare", severity="warning")
            return
        
        # Generate commands
        commands = self._generate_commands(dest, sources)
        
        # Generate scripts
        generator = ScriptGenerator()
        paths = generator.generate_all(
            commands=commands,
            device_ip=self.device_ip,
            username="admin",
            config=self.parser.config,
            description=f"Mirroring: {dest} <- {len(sources)} sources"
        )
        
        self.notify(f"Script generati in: {paths['bash'].parent}", severity="information")
    
    def action_apply(self) -> None:
        """Apply configuration to device."""
        if not self.is_connected:
            self.notify("Non connesso", severity="error")
            return
        
        dest = self.pending_dest
        sources = self.pending_sources
        
        if not dest or not sources:
            self.notify("Nessuna configurazione da applicare. Usa prima 'Configura'", severity="warning")
            return
        
        self._apply_config_worker(dest, sources)
    
    @work(exclusive=True, thread=True)
    def _apply_config_worker(self, dest: str, sources: List[str]) -> None:
        """Apply configuration in worker thread."""
        commands = self._generate_commands(dest, sources)
        
        self.notify("Applicazione in corso...", severity="information")
        
        success, output = self.ssh_manager.apply_mirroring_config(commands)
        
        if success:
            self.notify("Configurazione applicata!", severity="information")
            self.pending_dest = None
            self.pending_sources = []
            self._load_config_sync()
        else:
            self.notify(f"Errore: {output}", severity="error")
    
    def _generate_commands(self, dest: str, sources: List[str]) -> List[str]:
        """Generate mirroring commands."""
        commands = [f"no monitor session 1"]
        commands.append(f"monitor session 1 destination interface {dest}")
        
        for src in sorted(sources, key=lambda x: (int(x.split("/")[0]), int(x.split("/")[1]))):
            commands.append(f"monitor session 1 source interface {src}")
        
        commands.append("monitor session 1 mode")
        return commands
    
    def action_quit(self) -> None:
        """Quit application."""
        if self.is_connected:
            self.ssh_manager.disconnect()
        self.exit()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    app = PortMirroringApp()
    app.run()


if __name__ == "__main__":
    main()
