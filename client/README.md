# eTranslation client e callback server

Questa cartella contiene due componenti Python per l'[eTranslation REST API v2](../APIspecification/eTranslation-RestV2.yaml):

| File | Descrizione |
|---|---|
| `etranslation_client.py` | Client per gli endpoint `/askTranslate`, `/getDomains` e `/status` |
| `callback_server.py` | Server HTTP che riceve i callback `success`, `failure` e `delivery` |
| `callback_server.json` | Configurazione del server dei callback (host, porta, path) |
| `config.example.json` | Modello del file con le credenziali del client |
| `requirements.txt` | Dipendenze Python |

## Installazione

Richiede Python 3 e l'accesso a internet.

```bash
cd client
pip install -r requirements.txt
```

Il server dei callback usa solo la libreria standard, quindi non richiede dipendenze aggiuntive.

## Configurazione

### Credenziali del client

Le credenziali (fornite dal team eTranslation) servono per l'autenticazione HTTP Basic.

```bash
cp config.example.json config.json
```

Modifica `config.json`:

```json
{
  "username": "nome-applicazione",
  "password": "password"
}
```

`config.json` è escluso da git tramite [.gitignore](.gitignore). Non committarlo.

### Server dei callback

Impostazioni in [callback_server.json](callback_server.json):

```json
{
  "host": "127.0.0.1",
  "port": 8080,
  "success_path": "/etranslation/success",
  "failure_path": "/etranslation/failure",
  "delivery_path": "/etranslation/delivery"
}
```

| Chiave | Significato |
|---|---|
| `host` | Interfaccia di ascolto (`0.0.0.0` per accettare connessioni esterne) |
| `port` | Porta di ascolto |
| `success_path` / `failure_path` / `delivery_path` | Path dei tre callback. Devono iniziare con `/` e non essere uguali tra loro |

Le chiavi sconosciute vengono rifiutate.

## Utilizzo del client

### Esempio

Crea uno script nella cartella `client/`, per esempio `try_client.py`:

```python
from etranslation_client import ETranslationClient, ETranslationError

with ETranslationClient.from_config() as client:  # legge config.json
    print(client.get_status())

    try:
        request_id = client.translate_text(
            source_language="EN",
            target_languages=["FR", "DE"],
            text="Hello world",
            notifications={
                "success": {"http": "https://mio-host/etranslation/success"},
                "failure": {"http": "https://mio-host/etranslation/failure"},
            },
        )
        print("requestId:", request_id)
    except ETranslationError as exc:
        print("Errore eTranslation:", exc.error_code, exc.error_message)
```

```bash
cd client
python3 try_client.py
```

### Metodi principali

| Metodo | Descrizione |
|---|---|
| `ETranslationClient.from_config(path)` | Crea il client leggendo `config.json` (percorso predefinito) |
| `translate_text(...)` | Traduzione di un testo (massimo 5000 caratteri). Restituisce il `requestId` |
| `translate_document(...)` | Traduzione di un documento. Richiede `notifications` e `deliveries`. Restituisce il `requestId` |
| `get_domains()` | Coppie linguistiche disponibili per dominio |
| `get_status()` | Stato del servizio (`level` e `message`) |
| `inline_document(bytes, formato, nome)` | Helper per inviare un file in Base64 con `translate_document` |

`source_language` accetta `"LD"` per il rilevamento automatico della lingua, solo come lingua sorgente.

### Traduzione di un documento

```python
from etranslation_client import ETranslationClient, inline_document

with ETranslationClient.from_config() as client:
    with open("documento.docx", "rb") as f:
        document = inline_document(f.read(), "docx", "documento")

    request_id = client.translate_document(
        source_language="IT",
        target_languages=["EN"],
        document=document,  # oppure {"http": {...}}, {"ftp": "..."}, {"sftp": "..."}
        notifications={
            "success": {"http": "https://mio-host/etranslation/success"},
            "failure": {"http": "https://mio-host/etranslation/failure"},
        },
        deliveries={"http": "https://mio-host/etranslation/delivery"},
    )
```

### Glossario

Il parametro `glossary` (disponibile in `translate_text` e `translate_document`) permette di indicare termini che non devono essere tradotti, o che devono essere tradotti in modo specifico per il progetto.

Il glossario è una fonte file con la stessa struttura di `file` nella specifica: deve contenere esattamente una tra `ftp`, `sftp`, `http` o `document`. Il formato accettato è:

- un file `xlsx` con due colonne
- un file `tsv` senza intestazione

Per un file locale usa `inline_document`:

```python
from etranslation_client import ETranslationClient, inline_document

glossary_tsv = "turtle\tturtle\tturtle\tturtle\nRDF\tRDF\tRDF\tRDF\n"

with ETranslationClient.from_config() as client:
    request_id = client.translate_document(
        source_language="IT",
        target_languages=["EN", "FR"],
        document=inline_document(open("documento.docx", "rb").read(), "docx", "documento"),
        glossary=inline_document(glossary_tsv.encode("utf-8"), "tsv", "glossario"),
        notifications={
            "success": {"http": "https://mio-host/etranslation/success"},
            "failure": {"http": "https://mio-host/etranslation/failure"},
        },
        deliveries={"http": "https://mio-host/etranslation/delivery"},
    )
```

Se il glossario è già disponibile su un server, usa una fonte remota:

```python
glossary={"http": {"url": "https://mio-host/glossario.tsv", "format": "tsv", "method": "GET"}}
# oppure
glossary={"ftp": "ftp://server/percorso/glossario.xlsx"}
```

Note:

- Il glossario non è compatibile con l'LLM: se `llm` è attivo insieme al glossario, il servizio restituisce `GLOSSARY_AND_USE_LLM_MUTUALLY_EXCLUSIVE` (errore `-10419`). Il client non blocca questa combinazione, quindi l'errore arriva come `ETranslationError`.
- Il glossario è valido anche per le traduzioni di testo. In quel caso va passato a `translate_text` con la stessa struttura.

### Errori

- Errori di validazione lato client (lingua non valida, testo troppo lungo, notifiche malformate): `ValueError`, senza chiamare il servizio.
- Errori restituiti da eTranslation (HTTP 400 con `errorCode`): `ETranslationError`, con `error_code` e `error_message`.
- Altri errori HTTP: `requests.HTTPError`.

## Utilizzo del server dei callback

La traduzione è asincrona: il risultato arriva come callback agli URL indicati in `notifications` e `deliveries`. Il server deve quindi essere raggiungibile da internet, direttamente o tramite reverse proxy, e i path devono corrispondere a quelli usati nelle richieste.

### Avvio da riga di comando

```bash
cd client
python3 callback_server.py                       # usa callback_server.json
python3 callback_server.py --port 9000           # sovrascrive la porta
python3 callback_server.py --config altro.json   # file alternativo
```

Ogni callback ricevuto viene stampato in formato JSON. Il server risponde:

| Risposta | Quando |
|---|---|
| `200` | Callback valido ed elaborato |
| `400` | Body non JSON o campi obbligatori mancanti |
| `404` | Path non configurato |
| `500` | Errore nell'handler |

### Uso da codice

```python
from callback_server import CallbackHandlers, CallbackServer, CallbackServerConfig

def on_success(event):
    print("Traduzione completata:", event.request_id, event.translated_text)

def on_failure(event):
    print("Errore:", event.request_id, event.error_code, event.error_message)

def on_delivery(event):
    print("Risultato consegnato:", event.request_id, event.target_language)

handlers = CallbackHandlers(on_success=on_success, on_failure=on_failure, on_delivery=on_delivery)
config = CallbackServerConfig.from_file("callback_server.json")
CallbackServer(handlers, config).serve_forever()
```

Gli handler ricevono gli oggetti `SuccessNotification`, `FailureNotification` e `Delivery`. Gli handler non definiti accettano il callback senza elaborarlo.

## Note

- Il client usa il percorso `https://language-tools.ec.europa.eu/etranslation/api` come base. La specifica indica `/askTranslate` anche nel server, quindi il percorso va verificato con la documentazione eTranslation. Il parametro `base_url` permette di modificarlo.
- Il server dei callback non autentica le richieste in ingresso, perché la specifica non descrive un meccanismo per i callback. Valuta questo aspetto prima di esporlo pubblicamente.
- Il server usa HTTP semplice. In produzione serve HTTPS, gestito da un reverse proxy.
