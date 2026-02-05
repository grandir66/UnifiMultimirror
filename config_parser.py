#!/usr/bin/env python3
"""
Configuration Parser for Ubiquiti EdgeSwitch/UniFi switches.
Parses running-config, interface status, and port-channel outputs.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class InterfaceConfig:
    """Configuration for a single interface."""
    port_id: str
    description: str = ""
    link_state: str = "Unknown"  # Up, Down, Unknown
    speed: str = ""              # 10G Full, 25G Full, etc.
    media_type: str = ""         # DAC, 10GBase-SR, etc.
    pvid: int = 1                # Native/untagged VLAN
    tagged_vlans: List[int] = field(default_factory=list)
    untagged_vlans: List[int] = field(default_factory=list)
    is_shutdown: bool = False
    lag_member_of: str = ""      # LAG ID if member (3/1, 3/2, etc.)
    

@dataclass
class LAGConfig:
    """Configuration for a Link Aggregation Group."""
    lag_id: str                  # 3/1, 3/2, etc.
    name: str = ""               # ch1, ch2, etc.
    link_state: str = "Down"     # Up, Down
    lag_type: str = "Dynamic"    # Dynamic, Static
    member_ports: List[str] = field(default_factory=list)
    active_ports: List[str] = field(default_factory=list)


@dataclass
class MonitorSession:
    """Port mirroring session configuration."""
    session_id: int
    destination: str = ""
    sources: List[str] = field(default_factory=list)
    mode: str = ""


@dataclass
class SystemInfo:
    """System information from the switch."""
    hostname: str = ""
    description: str = ""
    software_version: str = ""
    uptime: str = ""
    ip_address: str = ""
    netmask: str = ""
    gateway: str = ""
    mgmt_vlan: int = 1


@dataclass
class SwitchConfig:
    """Complete switch configuration."""
    system_info: SystemInfo = field(default_factory=SystemInfo)
    interfaces: Dict[str, InterfaceConfig] = field(default_factory=dict)
    lags: Dict[str, LAGConfig] = field(default_factory=dict)
    monitor_sessions: Dict[int, MonitorSession] = field(default_factory=dict)
    vlans: List[int] = field(default_factory=list)


class ConfigParser:
    """Parser for Ubiquiti switch configuration outputs."""
    
    def __init__(self):
        self.config = SwitchConfig()
    
    # =========================================================================
    # VLAN list parsing utilities
    # =========================================================================
    
    @staticmethod
    def parse_vlan_list(vlan_str: str) -> List[int]:
        """
        Parse VLAN list string like "2,4-7,15-16,20,40" into list of integers.
        """
        vlans = []
        if not vlan_str:
            return vlans
        
        parts = vlan_str.replace(" ", "").split(",")
        for part in parts:
            if "-" in part:
                try:
                    start, end = part.split("-", 1)
                    vlans.extend(range(int(start), int(end) + 1))
                except ValueError:
                    continue
            else:
                try:
                    vlans.append(int(part))
                except ValueError:
                    continue
        
        return sorted(set(vlans))
    
    @staticmethod
    def format_vlan_list(vlans: List[int]) -> str:
        """
        Format list of VLAN IDs into compact string like "2,4-7,15-16,20".
        """
        if not vlans:
            return ""
        
        vlans = sorted(set(vlans))
        result = []
        start = vlans[0]
        end = vlans[0]
        
        for vlan in vlans[1:]:
            if vlan == end + 1:
                end = vlan
            else:
                if start == end:
                    result.append(str(start))
                else:
                    result.append(f"{start}-{end}")
                start = end = vlan
        
        # Add last range
        if start == end:
            result.append(str(start))
        else:
            result.append(f"{start}-{end}")
        
        return ",".join(result)
    
    # =========================================================================
    # Running config parser
    # =========================================================================
    
    def parse_running_config(self, config_text: str) -> None:
        """Parse running-config output."""
        lines = config_text.split("\n")
        
        current_interface: Optional[str] = None
        current_iface_config: Optional[InterfaceConfig] = None
        
        for line in lines:
            line = line.rstrip()
            stripped = line.strip()
            
            # Skip empty lines and prompts
            if not stripped or stripped.startswith("(UBNT)"):
                continue
            
            # System info from comments
            if stripped.startswith("!System Description"):
                match = re.search(r'"([^"]+)"', stripped)
                if match:
                    self.config.system_info.description = match.group(1)
            
            elif stripped.startswith("!System Software Version"):
                match = re.search(r'"([^"]+)"', stripped)
                if match:
                    self.config.system_info.software_version = match.group(1)
            
            elif stripped.startswith("!System Up Time"):
                match = re.search(r'"([^"]+)"', stripped)
                if match:
                    self.config.system_info.uptime = match.group(1)
            
            # Network parameters
            elif stripped.startswith("network parms"):
                parts = stripped.split()
                if len(parts) >= 4:
                    self.config.system_info.ip_address = parts[2]
                    self.config.system_info.netmask = parts[3]
                    if len(parts) >= 5:
                        self.config.system_info.gateway = parts[4]
            
            # Management VLAN
            elif stripped.startswith("network mgmt_vlan"):
                parts = stripped.split()
                if len(parts) >= 3:
                    try:
                        self.config.system_info.mgmt_vlan = int(parts[2])
                    except ValueError:
                        pass
            
            # Global VLAN database (only when NOT inside an interface block)
            elif stripped.startswith("vlan ") and "database" not in stripped and current_interface is None:
                # Global VLAN definition like "vlan 2,4-7,15-16,20,40,88,133,666"
                match = re.match(r"vlan\s+([\d,\-]+)$", stripped)
                if match:
                    self.config.vlans = self.parse_vlan_list(match.group(1))
            
            # Hostname
            elif stripped.startswith("snmp-server sysname"):
                match = re.search(r'"([^"]+)"', stripped)
                if match:
                    self.config.system_info.hostname = match.group(1)
            
            # Interface start
            elif stripped.startswith("interface "):
                # Save previous interface
                if current_interface and current_iface_config:
                    self.config.interfaces[current_interface] = current_iface_config
                
                match = re.match(r"interface\s+(0/\d+|lag\s+\d+|3/\d+)", stripped)
                if match:
                    current_interface = match.group(1).replace(" ", "")
                    current_iface_config = InterfaceConfig(port_id=current_interface)
                else:
                    current_interface = None
                    current_iface_config = None
            
            # Interface configuration lines
            elif current_iface_config:
                if stripped.startswith("description"):
                    match = re.search(r"'([^']*)'", stripped)
                    if match:
                        current_iface_config.description = match.group(1)
                
                elif stripped.startswith("vlan pvid"):
                    parts = stripped.split()
                    if len(parts) >= 3:
                        try:
                            current_iface_config.pvid = int(parts[2])
                        except ValueError:
                            pass
                
                elif stripped.startswith("vlan participation include"):
                    # vlan participation include shows VLANs the port participates in
                    # We store this separately - tagged_vlans comes from "vlan tagging"
                    vlan_str = stripped.replace("vlan participation include", "").strip()
                    vlans = self.parse_vlan_list(vlan_str)
                    # Store as participation VLANs (untagged + tagged combined)
                    current_iface_config.untagged_vlans = vlans
                
                elif stripped.startswith("vlan tagging"):
                    # vlan tagging specifies which VLANs are tagged (802.1Q)
                    # This is the authoritative source for tagged VLANs
                    vlan_str = stripped.replace("vlan tagging", "").strip()
                    current_iface_config.tagged_vlans = self.parse_vlan_list(vlan_str)
                
                elif stripped == "shutdown":
                    current_iface_config.is_shutdown = True
                
                elif stripped.startswith("addport"):
                    match = re.search(r"addport\s+(3/\d+)", stripped)
                    if match:
                        current_iface_config.lag_member_of = match.group(1)
                
                elif stripped == "exit":
                    # Save interface config
                    if current_interface and current_iface_config:
                        self.config.interfaces[current_interface] = current_iface_config
                    current_interface = None
                    current_iface_config = None
            
            # Monitor session
            elif stripped.startswith("monitor session"):
                match = re.match(
                    r"monitor session (\d+) (destination|source) interface (.+)",
                    stripped
                )
                if match:
                    session_id = int(match.group(1))
                    role = match.group(2)
                    interface = match.group(3).strip()
                    
                    if session_id not in self.config.monitor_sessions:
                        self.config.monitor_sessions[session_id] = MonitorSession(
                            session_id=session_id
                        )
                    
                    session = self.config.monitor_sessions[session_id]
                    if role == "destination":
                        session.destination = interface
                    else:
                        session.sources.append(interface)
                
                elif "mode" in stripped:
                    # monitor session 1 mode
                    match = re.match(r"monitor session (\d+) mode", stripped)
                    if match:
                        session_id = int(match.group(1))
                        if session_id in self.config.monitor_sessions:
                            self.config.monitor_sessions[session_id].mode = "enabled"
        
        # Save last interface if any
        if current_interface and current_iface_config:
            self.config.interfaces[current_interface] = current_iface_config
    
    # =========================================================================
    # Interface status parser
    # =========================================================================
    
    def parse_interfaces_status(self, status_text: str) -> None:
        """Parse 'show interfaces status all' output."""
        lines = status_text.split("\n")
        
        # Skip header lines
        in_data = False
        
        for line in lines:
            # Detect start of data after separator line
            if line.startswith("---------"):
                in_data = True
                continue
            
            if not in_data:
                continue
            
            # Parse port line
            # Format: Port Name State Mode Status Type Flow
            # Example: 0/3 SFP_ 3 - MONITORING PORT Up Auto D 10G Full DAC Inactive
            
            if not line.strip():
                continue
            
            # Port ID is the first field
            match = re.match(r"^(\d+/\d+)\s+", line)
            if not match:
                continue
            
            port_id = match.group(1)
            rest = line[match.end():]
            
            # Parse fixed-width columns (approximate positions)
            # Name: ~28 chars, State: ~8 chars, Mode: ~12 chars, Status: ~12 chars, Type: ~20 chars
            
            # Find Up or Down to locate state column
            state_match = re.search(r"\s+(Up|Down)\s+", rest)
            if state_match:
                name = rest[:state_match.start()].strip()
                state = state_match.group(1)
                after_state = rest[state_match.end():]
                
                # Parse remaining fields
                parts = after_state.split()
                
                # Mode + Status + Type + Flow
                mode = ""
                status = ""
                media_type = ""
                
                if parts:
                    # Mode (Auto D, 10G Full, 25G Full, etc.)
                    if parts[0] in ("Auto", "10G", "25G", "1G", "100M"):
                        mode = parts[0]
                        if len(parts) > 1 and parts[1] in ("D", "Full", "Half"):
                            mode += " " + parts[1]
                            parts = parts[2:]
                        else:
                            parts = parts[1:]
                    
                    # Status (actual speed)
                    if parts and parts[0] in ("10G", "25G", "1G", "100M"):
                        status = parts[0]
                        if len(parts) > 1 and parts[1] == "Full":
                            status += " Full"
                            parts = parts[2:]
                        else:
                            parts = parts[1:]
                    
                    # Media type
                    if parts:
                        media_type = parts[0]
                
                # Update interface config
                if port_id in self.config.interfaces:
                    iface = self.config.interfaces[port_id]
                    iface.link_state = state
                    iface.speed = status if status else mode
                    iface.media_type = media_type
                    if name and not iface.description:
                        iface.description = name
                else:
                    # Create interface if not exists
                    self.config.interfaces[port_id] = InterfaceConfig(
                        port_id=port_id,
                        description=name,
                        link_state=state,
                        speed=status if status else mode,
                        media_type=media_type
                    )
    
    # =========================================================================
    # Port-channel parser
    # =========================================================================
    
    def parse_port_channel_brief(self, pc_text: str) -> None:
        """Parse 'show port-channel brief' output."""
        lines = pc_text.split("\n")
        
        in_data = False
        
        for line in lines:
            # Detect start of data after separator line
            if line.startswith("---------"):
                in_data = True
                continue
            
            if not in_data:
                continue
            
            if not line.strip():
                continue
            
            # Format: LogicalIf Name Min State Trap Type MbrPorts ActivePorts
            # Example: 3/1 ch1 1 Up Disabled Dynamic 0/31,0/32 0/31,0/32
            
            match = re.match(
                r"^(\d+/\d+)\s+(\S+)\s+(\d+)\s+(Up|Down)\s+(\S+)\s+(Dynamic|Static)\s*(.*)$",
                line
            )
            
            if match:
                lag_id = match.group(1)
                name = match.group(2)
                state = match.group(4)
                lag_type = match.group(6)
                ports_str = match.group(7).strip()
                
                # Parse member and active ports
                member_ports = []
                active_ports = []
                
                if ports_str:
                    parts = ports_str.split()
                    if len(parts) >= 1:
                        member_ports = [p.strip() for p in parts[0].split(",") if p.strip()]
                    if len(parts) >= 2:
                        active_ports = [p.strip() for p in parts[1].split(",") if p.strip()]
                
                self.config.lags[lag_id] = LAGConfig(
                    lag_id=lag_id,
                    name=name,
                    link_state=state,
                    lag_type=lag_type,
                    member_ports=member_ports,
                    active_ports=active_ports
                )
    
    # =========================================================================
    # Convenience methods
    # =========================================================================
    
    def get_physical_ports(self) -> List[str]:
        """Get list of physical port IDs (0/x format)."""
        return sorted(
            [p for p in self.config.interfaces.keys() if p.startswith("0/")],
            key=lambda x: int(x.split("/")[1])
        )
    
    def get_lag_ports(self) -> List[str]:
        """Get list of LAG port IDs (3/x format)."""
        return sorted(
            [p for p in self.config.lags.keys()],
            key=lambda x: int(x.split("/")[1])
        )
    
    def get_mirroring_destination(self, session_id: int = 1) -> Optional[str]:
        """Get the destination port for a mirroring session."""
        if session_id in self.config.monitor_sessions:
            return self.config.monitor_sessions[session_id].destination
        return None
    
    def get_mirroring_sources(self, session_id: int = 1) -> List[str]:
        """Get list of source ports for a mirroring session."""
        if session_id in self.config.monitor_sessions:
            return self.config.monitor_sessions[session_id].sources
        return []
    
    def is_mirroring_source(self, port_id: str, session_id: int = 1) -> bool:
        """Check if port is a mirroring source."""
        return port_id in self.get_mirroring_sources(session_id)
    
    def is_mirroring_destination(self, port_id: str, session_id: int = 1) -> bool:
        """Check if port is the mirroring destination."""
        return port_id == self.get_mirroring_destination(session_id)


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    # Test with sample config
    sample_config = """
!System Description "USW-Pro-Aggregation, 7.1.26.15869, Linux 4.4.153"
!System Software Version "7.1.26.15869"
snmp-server sysname "SW-CED-AGG-243"
network parms 192.168.40.243 255.255.255.0 192.168.40.254
network mgmt_vlan 40
vlan database
vlan 2,4-7,15-16,20,40,88,133,666
exit

interface 0/3
description 'SFP_ 3 - MONITORING PORT'
vlan participation include 2,4-7,15-16,20,40,88,133,666
vlan tagging 2,4-7,15-16,20,40,88,133,666
exit

interface 0/4
description 'SFP_ 4 - SW CED 237'
vlan participation include 2,4-7,15-16,20,40,88,133,666
vlan tagging 2,4-7,15-16,20,40,88,133,666
exit

monitor session 1 destination interface 0/3
monitor session 1 source interface 0/4
monitor session 1 source interface 0/8
monitor session 1 mode
"""
    
    parser = ConfigParser()
    parser.parse_running_config(sample_config)
    
    print(f"Hostname: {parser.config.system_info.hostname}")
    print(f"VLANs: {parser.config.vlans}")
    print(f"Interfaces: {list(parser.config.interfaces.keys())}")
    print(f"Monitor destination: {parser.get_mirroring_destination()}")
    print(f"Monitor sources: {parser.get_mirroring_sources()}")
