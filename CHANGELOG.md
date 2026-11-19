# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/it/1.1.0/).

## [Non rilasciato]

### Aggiunto
- **Dialetto Enterprise** (20/11/2026, `dialetti.py`): gli USW Enterprise (SW-LAB-ENT8) hanno una CLI di tipo
  Cisco, porte `tw1-8`/`te1-2`, niente `monitor session 1 mode`, e la sessione non compare nella running-config.
  La TUI riconosce il dialetto dalla running-config, legge porte e sessione, manda i comandi giusti (destinazione
  `network`, così l'apparato collegato resta gestibile) e verifica con `show monitor session 1`. Anche gli script
  generati usano apertura e chiusura del dialetto. Il menu classico (`main.py`) resta solo EdgeSwitch.

### Modificato
- Paginazione «More: <space>» dell'Enterprise gestita: prima la running-config si fermava alla prima pagina.
- La TUI ricrea il parser a ogni lettura: prima le sorgenti si accumulavano a ogni ricarica.
- **Applica verifica sullo switch** (19/11/2026): prima diceva «applicata» anche se lo
  switch rifiutava un comando. Ora legge gli errori della CLI e rilegge la configurazione;
  il successo arriva solo se destinazione, sorgenti e sessione attiva combaciano. La TUI
  ricarica comunque la tabella, così mostra lo stato vero.
- La TUI chiede anche l'utente SSH (19/11/2026): era fisso `admin`, ma gli switch di un altro sito
  possono avere un utente diverso (impostato nella console UniFi del sito).
- README: avvio con `.venv` (la TUI non partiva dal vecchio `ssh_env/`, privo di textual).
