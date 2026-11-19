# TASKS — Script_Ubiquiti

## 2026-11-19 — switch su cui serve il mirroring

Riccardo, 19/11: gli switch sono **l'aggregator** e **il 48 PoE del CED**, più
**l'Enterprise**, oggi non raggiungibile perché collegato alla UCG. Indirizzi e nomi
fuori da questo repo, che è pubblico (vedi `config.json` e l'inventario di Zabbix).

- [x] Aggregator: configurazione già pronta in `generated/` (07/05/2026, destinazione
      0/3, 35 sorgenti). SSH raggiungibile il 19/11.
- [ ] 48 PoE del CED: nessuna configurazione. Servono la porta di destinazione e le
      sorgenti. SSH raggiungibile il 19/11; la CLI (`monitor session`) non è ancora provata.
- [ ] Enterprise: da fare quando sarà raggiungibile (oggi dietro la UCG).
      Riccardo, 19/11: pensare a una VPN fra le due reti; proposta in `DA-Infra/TASKS.md` (disegno del LAB).
      19/11: scelta la VPN WireGuard della UCG del LAB (server LAB-IT, creato); dettagli in `DA-Infra/TASKS.md`.
      19/11: tunnel attivo, SSH dell'Enterprise raggiungibile. Riccardo: **destinazione porta 8 (LECS, l'NDR)**, si
      fa via SSH/CLI con questo strumento, non dall'interfaccia UniFi. Porte (console, 19/11): 1 SW-LAB-01, 2 SW-LAB-05,
      3 SW-LAB-02, 4 SW-LAB-03, 5 AP AC LR, 6-7 libere, 8 LECS (2,5 GbE), 9 SFP+ 1 libera, 10 SFP+ 2 uplink 10G
      verso la UCG. Firmware 7.6.11. Da decidere: sorgenti. Da chiarire: il LECS ha un indirizzo di gestione
      sulla stessa porta 8 (una porta di destinazione di solito non inoltra traffico normale). Servono le
      credenziali SSH degli apparati del sito LAB (non sono nel vault). Dal 19/11 la TUI chiede anche l'utente.
      **Riccardo, 19/11: sorgente solo l'uplink SFP+ 2** (porta 10). Comandi attesi: `no monitor session 1`,
      `monitor session 1 destination interface 0/8`, `monitor session 1 source interface 0/10`,
      `monitor session 1 mode` (nomi delle porte da confermare con `show interfaces status all`).
      19/11: credenziale nel vault (`da-lab-switch-accessi.md`, righe 3 e 6 uguali, utente admin). **Lo switch la
      rifiuta** (dropbear, accetta publickey e password): due tentativi, poi fermo. Da verificare con Riccardo la
      «Device Authentication» del sito LAB. Lo strumento ora usa solo la password (niente chiavi né agente).
- [ ] Da decidere: scelta dello switch all'avvio (oggi `config.json` ne ricorda uno solo).
