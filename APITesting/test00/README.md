# Test 00 - Interrogazione Domini e Coppie Linguistiche (/getDomains)

Questo test verifica l'invocazione dell'endpoint `/getDomains` dell'API REST v2 di eTranslation, utilizzando il client Python presente in `implementation/etranslation_client.py`.

## Scopo del Test

L'endpoint `/getDomains` (documentato in `APISpecification/eTranslation-RestV2.yaml` riga 422) consente di recuperare l'elenco completo dei domini di traduzione attivi (ad esempio `GEN` per testo generale, `SPD` per documenti specifici) e, per ciascun dominio, tutte le coppie linguistiche sorgente-destinazione abilitate (es. `IT-EN`, `IT-DE`, `EN-IT`, `EN-DE`). Nelle specifiche, la presenza di coppie con suffisso `_LLM` indica inoltre il supporto all'arricchimento tramite Large Language Model.

Questo test serve a:
1. **Verificare la connettività e l'autenticazione** con l'API eTranslation con una chiamata sincrona e leggera (senza dover avviare un callback server).
2. **Validare preventivamente** se una coppia linguistica (come `IT-EN` e `IT-DE` usate in [test01](../test01/README.md) o `EN-IT` e `EN-DE` in [test02](../test02/README.md)) è supportata in un determinato dominio prima di inviare richieste di traduzione.

## Struttura della cartella

```
APITesting/test00/
├── README.md               # Documentazione e guida all'uso del test
├── run_get_domains.py      # Script eseguibile da CLI per interrogare /getDomains
├── test_get_domains.py     # Suite di test unitari con mock (unittest standard)
└── config.example.json     # Template per le credenziali
```

## Esecuzione dei Test Unitari (senza credenziali)

I test unitari verificano la correttezza del metodo HTTP (`GET`), dell'endpoint (`/getDomains`), dell'autenticazione Basic, del parsing della risposta JSON e della gestione degli errori (es. HTTP 400 `NOT_AUTHORIZED` tramite `ETranslationError`), senza richiedere connessione di rete né credenziali:

```bash
python3 -m unittest APITesting/test00/test_get_domains.py
```

## Esecuzione dello Script CLI (`run_get_domains.py`)

### 1. Modalità Dry-run (Verifica senza chiamata di rete)

Mostra l'endpoint a cui verrebbe inviata la richiesta senza contattare l'API:

```bash
python3 APITesting/test00/run_get_domains.py --dry-run
```

### 2. Chiamata reale all'API eTranslation

Configura le credenziali in uno dei seguenti modi:
1. Copia [config.example.json](config.example.json) in `config.json` nella cartella `test00/`:
   ```bash
   cp APITesting/test00/config.example.json APITesting/test00/config.json
   ```
2. Oppure utilizza il file `config.json` già configurato in `APITesting/test01/config.json`, `APITesting/test02/config.json` o `implementation/config.json` (lo script li ricerca automaticamente).
3. Oppure imposta le variabili d'ambiente:
   ```bash
   export ETRANSLATION_USERNAME="il-tuo-username"
   export ETRANSLATION_PASSWORD="la-tua-password"
   ```

Esegui la chiamata:

```bash
python3 APITesting/test00/run_get_domains.py
```

### Opzioni dello Script

| Parametro | Descrizione | Default |
|---|---|---|
| `--domain <NAME>` | Filtra l'output mostrando solo il dominio specificato (es. `GEN`, `SPD`) | Tutti i domini |
| `--check-pair <P1 P2 ...>` | Uno o più codici coppia linguistica da verificare (es. `IT-EN IT-DE EN-IT`) | `IT-EN IT-DE` |
| `--output-json <path>` | Salva il payload JSON grezzo ricevuto dall'API su un file | Nessuno |
| `--config <path>` | Percorso esplicito al file `config.json` | Ricerca automatica |
| `--dry-run` | Simula l'esecuzione senza effettuare chiamate di rete | `False` |

#### Esempi di utilizzo avanzato:

- Verificare il supporto per le coppie inglese-italiano e inglese-tedesco nel dominio `GEN`:
  ```bash
  python3 APITesting/test00/run_get_domains.py --domain GEN --check-pair EN-IT EN-DE
  ```

- Esportare l'intero catalogo dei domini su file per analisi:
  ```bash
  python3 APITesting/test00/run_get_domains.py --output-json catalogo_domini.json
  ```
