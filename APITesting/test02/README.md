# Test 01 - Chiamata eTranslation API con Glossario

Questo test verifica l'invocazione dell'API REST v2 di eTranslation utilizzando il client Python presente in `implementation/etranslation_client.py`.

## Specifiche del Test

- **Testo da tradurre:** `Validatore dei file turtle (.ttl)`
- **Lingua sorgente:** `IT` (Italiano)
- **Lingue di destinazione:** `EN`, `DE` (Inglese, Tedesco)
- **Glossario:** file TSV ([glossary.tsv](glossary.tsv)) che mantiene il termine `turtle` invariato da italiano verso inglese e tedesco (poiché fa riferimento al formato RDF Turtle `.ttl` e non alla tartaruga animale).

## Struttura della cartella

```
APITesting/test01/
├── README.md               # Documentazione e istruzioni
├── glossary.tsv            # File del glossario TSV (turtle -> turtle, turtle)
├── run_test.py             # Script eseguibile da riga di comando (supporta --dry-run)
├── test_translation.py     # Suite di test unitari con mock (unittest standard)
└── config.example.json     # Template per le credenziali
```

## Esecuzione dei Test Unitari (senza credenziali)

I test unitari verificano la composizione del payload, la codifica Base64 del glossario TSV, la gestione delle risposte del client e degli errori eTranslation tramite mock:

```bash
python3 -m unittest APITesting/test01/test_translation.py
```

## Esecuzione dello Script di Chiamata

### 1. Modalità Dry-run (Verifica payload)

Non effettua chiamate di rete e mostra il payload JSON esatto inviato a `/askTranslate`:

```bash
python3 APITesting/test01/run_test.py --dry-run
```

### 2. Chiamata reale all'API eTranslation

Configura le credenziali in uno dei seguenti modi:
1. Copia [config.example.json](config.example.json) in `config.json` e inserisci le tue credenziali:
   ```bash
   cp APITesting/test01/config.example.json APITesting/test01/config.json
   ```
2. Oppure imposta le variabili d'ambiente:
   ```bash
   export ETRANSLATION_USERNAME="il-tuo-username"
   export ETRANSLATION_PASSWORD="la-tua-password"
   ```

Esegui lo script:

```bash
python3 APITesting/test01/run_test.py
```

Opzioni disponibili:
- `--callback-url <URL>`: Specifica un URL HTTP per ricevere il callback di successo con il testo tradotto.
- `--text "<testo>"`: Modifica il testo da tradurre.
- `--source <LANG>`: Lingua sorgente (default: `IT`).
- `--targets <LANG ...>`: Lingue destinazione (default: `EN DE`).
- `--glossary <path>`: Percorso personalizzato del file glossario.

## Note sul Glossario

Secondo le specifiche di [eTranslation-RestV2.yaml](../../APISpecification/eTranslation-RestV2.yaml):
- Il glossario può essere un file TSV privo di intestazioni (`headerless`) o un file XLSX a due colonne.
- Per il TSV a tre colonne (IT, EN, DE):
  ```
  turtle	turtle	turtle
  ```
- Qualora il backend eTranslation richieda l'uso del glossario solo su documenti (errore `-10418 GLOSSARY_NOT_SUPPORTED_WITH_SNIPPET`), è possibile inviare il testo come documento `.txt` usando `translate_document()`.
