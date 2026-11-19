#!/usr/bin/env python3
"""
Dialetti CLI degli switch UniFi per il port mirroring.

- EDGESWITCH: aggregator e switch con CLI EdgeSwitch (`cli`, `enable`, porte `0/3`,
  `monitor session 1 mode`, sessione visibile nella running-config).
- ENTERPRISE: USW Enterprise (es. SW-LAB-ENT8, firmware 7.6), CLI di tipo Cisco: porte
  `TwoPointFiveGigabitEthernet8` (breve `tw8`) e `TenGigabitEthernet2` (`te2`), niente
  `mode`, sessione **non** visibile nella running-config: si legge con
  `show monitor session 1`.

Trappola (20/11/2026, SW-LAB-ENT8): su questa CLI `comando ?` seguito da Invio esegue
il comando se è già completo. Lo strumento non usa mai `?`.
"""

import re
from typing import Iterable, List, Optional, Tuple

EDGESWITCH = "edgeswitch"
ENTERPRISE = "enterprise"

# prefisso breve -> nome lungo della CLI Enterprise, nell'ordine in cui si mostrano
PREFISSI = [
    ("gi", "GigabitEthernet"),
    ("tw", "TwoPointFiveGigabitEthernet"),
    ("te", "TenGigabitEthernet"),
]
_DA_LUNGO = {lungo.lower(): breve for breve, lungo in PREFISSI}
_DA_BREVE = {breve: lungo for breve, lungo in PREFISSI}
_RE_LUNGO = re.compile(r"^(TwoPointFiveGigabitEthernet|TenGigabitEthernet|GigabitEthernet)(\d+)$", re.I)
_RE_BREVE = re.compile(r"^(gi|tw|te)(\d+)$", re.I)


def rileva(running_config: str) -> str:
    """Riconosce il dialetto dalla running-config."""
    if re.search(r"^interface\s+(TwoPointFiveGigabitEthernet|TenGigabitEthernet|GigabitEthernet)\d+",
                 running_config, re.M | re.I):
        return ENTERPRISE
    return EDGESWITCH


def nome_breve(nome: str) -> str:
    """'TwoPointFiveGigabitEthernet8' -> 'tw8'; un nome già breve resta com'è."""
    m = _RE_LUNGO.match(nome.strip())
    if m:
        return f"{_DA_LUNGO[m.group(1).lower()]}{m.group(2)}"
    return nome.strip().lower() if _RE_BREVE.match(nome.strip()) else nome.strip()


def nome_cli(porta: str) -> str:
    """'tw8' -> 'TwoPointFiveGigabitEthernet8' (per i comandi Enterprise)."""
    m = _RE_BREVE.match(porta.strip())
    if m:
        return f"{_DA_BREVE[m.group(1).lower()]}{m.group(2)}"
    return porta.strip()


def chiave_porta(porta: str) -> Tuple[int, int, str]:
    """Ordinamento valido per i due dialetti: '0/3', '3/1', 'tw8', 'te2'."""
    m = re.match(r"^(\d+)/(\d+)$", porta)
    if m:
        return (int(m.group(1)), int(m.group(2)), "")
    m = _RE_BREVE.match(porta)
    if m:
        ordine = [b for b, _ in PREFISSI].index(m.group(1).lower())
        return (100 + ordine, int(m.group(2)), "")
    return (999, 0, porta)


def comandi_mirror(dialetto: str, destinazione: str, sorgenti: Iterable[str],
                   attuale_dest: Optional[str] = None,
                   attuali_sorgenti: Iterable[str] = ()) -> List[str]:
    """Comandi (già dentro `configure`) per impostare la sessione 1."""
    sorgenti = sorted(set(sorgenti), key=chiave_porta)
    if dialetto == ENTERPRISE:
        cmds: List[str] = []
        # le sorgenti che non servono più vanno tolte una per una
        for vecchia in sorted(set(attuali_sorgenti) - set(sorgenti), key=chiave_porta):
            cmds.append(f"no monitor session 1 source interface {nome_cli(vecchia)}")
        if attuale_dest and attuale_dest != destinazione:
            cmds.append("no monitor session 1 destination")
        # «network»: la destinazione continua a far passare il traffico normale
        # (la gestione dell'apparato collegato, es. il LECS)
        cmds.append(f"monitor session 1 destination interface {nome_cli(destinazione)} network")
        cmds += [f"monitor session 1 source interface {nome_cli(s)} both" for s in sorgenti]
        return cmds
    cmds = ["no monitor session 1", f"monitor session 1 destination interface {destinazione}"]
    cmds += [f"monitor session 1 source interface {s}" for s in sorgenti]
    cmds.append("monitor session 1 mode")
    return cmds


def comando_lettura_sessione(dialetto: str) -> Optional[str]:
    """Comando che mostra la sessione 1 (None = si legge dalla running-config)."""
    return "show monitor session 1" if dialetto == ENTERPRISE else None


def _espandi(token: str) -> List[str]:
    """'tw1-tw3' o 'tw1-3' -> tw1, tw2, tw3; 'te2' -> te2."""
    m = re.match(r"^(gi|tw|te)(\d+)-(?:(gi|tw|te))?(\d+)$", token, re.I)
    if m:
        pre = m.group(1).lower()
        return [f"{pre}{n}" for n in range(int(m.group(2)), int(m.group(4)) + 1)]
    return [token.lower()]


def leggi_sessione(testo: str) -> Tuple[Optional[str], List[str], bool]:
    """
    Interpreta `show monitor session 1` della CLI Enterprise:
        Session 1:
             Type: SPAN
             Destination: tw8, network port
             Source: port te2, both
    Ritorna (destinazione, sorgenti, la sessione esiste).
    """
    dest: Optional[str] = None
    sorgenti: List[str] = []
    for riga in testo.splitlines():
        r = riga.strip()
        if r.lower().startswith("destination:"):
            m = re.search(r"\b((?:gi|tw|te)\d+)\b", r, re.I)
            if m:
                dest = m.group(1).lower()
        elif r.lower().startswith("source:"):
            for tok in re.findall(r"\b(?:gi|tw|te)\d+(?:-(?:gi|tw|te)?\d+)?\b", r, re.I):
                sorgenti.extend(_espandi(tok))
    esiste = dest is not None or bool(sorgenti)
    return dest, sorted(set(sorgenti), key=chiave_porta), esiste
