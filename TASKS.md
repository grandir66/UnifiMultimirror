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
- [ ] Da decidere: scelta dello switch all'avvio (oggi `config.json` ne ricorda uno solo).
