# UnifiMultimirror

Tool per la gestione del **port mirroring multi-porta** su switch Ubiquiti UniFi/EdgeSwitch.

Il controller UniFi supporta nativamente solo una singola porta in mirroring. Questo tool permette di configurare **multiple porte source** via CLI SSH, superando questa limitazione.

## Caratteristiche

- **Interfaccia TUI** (Text User Interface) con navigazione da tastiera
- **Visualizzazione porte** con stato link, VLAN (PVID e Tagged), ruolo mirroring
- **Configurazione interattiva** con selezione checkbox delle porte source
- **Generazione script** riutilizzabili (Bash, Python, comandi puri)
- **Applicazione diretta** della configurazione via SSH
- Supporto per **porte fisiche** e **LAG** (Link Aggregation Groups)

## Screenshot

```
┌──────────────────────────────────────────────────────────────────────────────┐
│     │ Porta │ Descrizione              │ Stato │ PVID │ Tagged        │ Ruolo│
├─────┼───────┼──────────────────────────┼───────┼──────┼───────────────┼──────┤
│ ◀◀  │ 0/3   │ SFP_ 3 - MONITORING PORT │ UP    │ 1    │ 2,4-7,15-16.. │ DEST │
│ [X] │ 0/4   │ SFP_ 4 - SW CED 237      │ UP    │ 1    │ 2,4-7,15-16.. │ SRC  │
│ [ ] │ 0/5   │ SFP_ 5 - SW 239 CLIENT   │ UP    │ 1    │ 2,4-7,15-16.. │ -    │
│ [X] │ 0/8   │ SFP_ 8 - SW CED 245 AP   │ UP    │ 1    │ 2,4-7,15-16.. │ SRC  │
└─────┴───────┴──────────────────────────┴───────┴──────┴───────────────┴──────┘
```

## Requisiti

- Python 3.8+
- Switch Ubiquiti UniFi o EdgeSwitch con accesso SSH abilitato
- Credenziali admin

## Installazione

```bash
# Clona il repository
git clone https://github.com/tuousername/UnifiMultimirror.git
cd UnifiMultimirror

# Installa le dipendenze
pip install -r requirements.txt
```

### Dipendenze

- `paramiko` - Connessione SSH
- `cryptography` - Crittografia password
- `rich` - Formattazione output CLI
- `textual` - Interfaccia TUI

## Utilizzo

### Interfaccia TUI (consigliata)

```bash
python tui_app.py
```

**Navigazione:**
- `↑/↓` - Muovi cursore
- `Spazio/Enter` - Seleziona/deseleziona porta source
- `D` - Imposta porta come destination
- `A` - Seleziona tutte le porte
- `N` - Deseleziona tutte
- `F10` - Conferma configurazione
- `ESC` - Annulla

**Schermata principale:**
- `R` - Ricarica configurazione dal device
- `C` - Configura mirroring
- `G` - Genera script
- `F5` - Applica configurazione
- `Q` - Esci

### Interfaccia CLI classica

```bash
python main.py
```

Menu testuale con opzioni numerate.

## Script Generati

Quando selezioni "Genera Script", vengono creati 3 file nella cartella `generated/`:

| File | Descrizione |
|------|-------------|
| `mirror_config_*.sh` | Script Bash (richiede `sshpass`) |
| `mirror_config_*.py` | Script Python standalone |
| `mirror_commands_*.txt` | Comandi puri per uso manuale |

### Esempio script Bash

```bash
./generated/mirror_config_20260205_143000.sh
# oppure con password come argomento
./generated/mirror_config_20260205_143000.sh "mypassword"
```

## Comandi CLI EdgeSwitch

Il tool genera automaticamente i seguenti comandi:

```
cli
enable
configure
no monitor session 1                              # Rimuove sessione esistente
monitor session 1 destination interface 0/3      # Porta monitor
monitor session 1 source interface 0/4           # Porta da monitorare
monitor session 1 source interface 0/8           # Altra porta source
...
monitor session 1 mode                            # Attiva sessione
exit
```

## Note Importanti

- Le modifiche via CLI sono **temporanee** e potrebbero essere sovrascritte dal controller UniFi al prossimo provisioning
- Usa gli script generati per **riapplicare** la configurazione dopo un reboot o provisioning
- L'utente SSH deve essere `admin`

## Struttura Progetto

```
UnifiMultimirror/
├── tui_app.py          # Interfaccia TUI (Textual)
├── main.py             # Interfaccia CLI classica
├── ssh_manager.py      # Gestione connessione SSH
├── config_parser.py    # Parser configurazione switch
├── ui.py               # UI per CLI classica (Rich)
├── script_generator.py # Generatore script
├── requirements.txt    # Dipendenze Python
├── generated/          # Script generati
│   └── .gitkeep
└── README.md
```

## Compatibilità

Testato su:
- USW-Pro-Aggregation (firmware 7.1.26)
- Altri switch UniFi/EdgeSwitch con CLI simile

## Licenza

MIT License

## Autore

Progetto sviluppato per semplificare la gestione del port mirroring multi-porta su reti Ubiquiti.
