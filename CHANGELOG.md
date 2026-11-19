# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/it/1.1.0/).

## [Non rilasciato]

### Modificato
- **Applica verifica sullo switch** (19/11/2026): prima diceva «applicata» anche se lo
  switch rifiutava un comando. Ora legge gli errori della CLI e rilegge la configurazione;
  il successo arriva solo se destinazione, sorgenti e sessione attiva combaciano. La TUI
  ricarica comunque la tabella, così mostra lo stato vero.
- README: avvio con `.venv` (la TUI non partiva dal vecchio `ssh_env/`, privo di textual).
