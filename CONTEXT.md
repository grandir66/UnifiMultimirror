# CONTEXT.md — Script_Ubiquiti (UnifiMultimirror)

> Completato il 19/11/2026 da un'analisi del codice (nessuna prova sullo switch).

## 1. Cos'è e perché esiste

Imposta il **port mirroring di più porte sorgente** sugli switch UniFi/EdgeSwitch via
SSH: il controller UniFi ne prevede una sola. Remote pubblico
`github.com/grandir66/UnifiMultimirror`. Stato: **manutenzione** (resta, è usato).
Switch interessati (Riccardo, 19/11): l'aggregator (USW-Pro-Aggregation; script pronto del
07/05/2026, destinazione 0/3, 35 sorgenti), il 48 PoE del CED (niente di pronto) e
l'Enterprise (oggi dietro la UCG, non raggiungibile). Indirizzi fuori dal repo; stato in `TASKS.md`.

## 2. Come è fatto

- `tui_app.py` (Textual): l'interfaccia consigliata. Login, tabella porte, scelta
  sorgenti/destinazione, genera script, applica (F5).
- `main.py` + `ui.py` (Rich): la stessa cosa a menu numerati, doppione della TUI.
- `ssh_manager.py`: paramiko `invoke_shell` → `cli` → `enable` → `configure`; lettura di
  `show running-config`, `show interfaces status all`, `show port-channel brief`.
- `config_parser.py`: interpreta quelle uscite (porte, LAG, VLAN, sessione monitor).
- `script_generator.py`: scrive in `generated/` `.sh` (sshpass), `.py`, `.txt`.
- `dialetti.py` (20/11): EdgeSwitch (aggregator, porte `0/x`) ed Enterprise (USW Enterprise, CLI tipo Cisco,
  porte `tw`/`te`, sessione letta da `show monitor session 1`, destinazione `network`). Lo usa la TUI;
  `main.py`/`ui.py` restano EdgeSwitch.
- `ssh_script.py` + `setup_and_run.sh` + `comandi.txt`: esecutore SSH generico più vecchio,
  è quello per cui esiste il venv `ssh_env/` (solo paramiko).

Comandi applicati: `no monitor session 1`, `monitor session 1 destination interface X`,
una riga `source interface` per porta, `monitor session 1 mode`.

## 3. Trappole

- **Il controller UniFi sovrascrive** la configurazione CLI al provisioning o al riavvio:
  dopo ogni provisioning va riapplicata (con gli script in `generated/`).
- **Dal 19/11 «Applica» verifica**: `apply_mirroring_config` legge gli errori della CLI per
  ogni comando e poi rilegge `show running-config` (destinazione, sorgenti, `mode`); il
  successo arriva solo se combaciano. Gli intervalli tipo `0/8-0/9` sono espansi. Non
  provato su uno switch vero: se la CLI scrive le sorgenti in una forma diversa, la
  verifica dà «fallita» e lo si vede nel messaggio.
- Ambiente: `.venv/` (python 3.12, textual 8) per la TUI; `ssh_env/` è solo per il vecchio
  `ssh_script.py`. La TUI con textual 8 arriva al login (prova del 19/11).
- `config.json` + `.ssh_key` (git-ignored): password cifrata con chiave nello stesso posto,
  è offuscamento. `old_config.json` (password in chiaro) tolto il 19/11.
- Host key SSH accettata senza verifica (`AutoAddPolicy`).
- Repo pubblico: niente IP, nomi di clienti o script generati nei commit (`generated/*` è
  ignorato; storia controllata il 19/11, pulita).
- Enterprise: `comando ?` + Invio **esegue** il comando se completo (20/11): lo strumento non usa mai `?`.
- Credenziali degli switch di un sito: Devices → «Device Updates & Settings» → «Device SSH Settings» (non la
  pagina Gestione, che è la console). Enterprise del LAB: vault `da-lab-switch-accessi.md`, via VPN LAB-IT.
