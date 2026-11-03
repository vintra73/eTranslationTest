# Test 02 - Chiamata eTranslation API con Glossario (EN -> IT, DE)

Questo test verifica l'invocazione dell'API REST v2 di eTranslation utilizzando il client Python presente in `implementation/etranslation_client.py`.

A differenza di [Test 01](../test01/README.md) (in cui la lingua sorgente era l'italiano), questo test effettua la traduzione a partire dall'inglese (**EN**) verso l'italiano (**IT**) e il tedesco (**DE**).

## Specifiche del Test

- **Testo da tradurre:** `Validator of turtle files (.ttl)` (equivalente in lingua sorgente EN del concetto *"Turtle (.ttl) file validator"*, personalizzabile anche con `--text`)
- **Lingua sorgente:** `EN` (Inglese)
- **Lingue di destinazione:** `IT`, `DE` (Italiano, Tedesco)
- **Glossario:** file TSV ([glossary.tsv](glossary.tsv)) che mappa il termine sorgente `turtle` (EN) preservandolo identico sia in italiano (`turtle`, evitando che venga tradotto con *"tartaruga"*) sia in tedesco (`turtle`, evitando *"Schildkröte"*).

## Struttura della cartella

```
APITesting/test02/
├── README.md               # Documentazione e istruzioni
├── glossary.tsv            # File del glossario TSV (EN -> IT, DE)
├── run_test.py             # Script eseguibile da riga di comando (supporta --dry-run)
├── test_translation.py     # Suite di test unitari con mock (unittest standard)
└── config.example.json     # Template per le credenziali
```

## Struttura del Glossario TSV

Il file [glossary.tsv](glossary.tsv) è un file privo di intestazione con colonne separate da tabulazione che seguono l'ordine: sorgente (`EN`) e destinazioni (`IT`, `DE`):

```tsv
turtle	turtle	turtle
```

## Esecuzione dei Test Unitari (senza credenziali)

I test unitari verificano la composizione del payload, la codifica Base64 del glossario TSV, la gestione delle risposte del client e degli errori eTranslation tramite mock:

```bash
python3 -m unittest APITesting/test02/test_translation.py
```

## Esecuzione dello Script di Chiamata

### 1. Modalità Dry-run (Verifica payload)

Non effettua chiamate di rete e mostra il payload JSON inviato a `/askTranslate`:

```bash
python3 APITesting/test02/run_test.py --dry-run
```

### 2. Chiamata reale all'API eTranslation

Configura le credenziali in uno dei seguenti modi:
1. Copia [config.example.json](config.example.json) in `config.json` e inserisci le tue credenziali:
   ```bash
   cp APITesting/test02/config.example.json APITesting/test02/config.json
   ```
2. Oppure usa il file `config.json` già configurato in `APITesting/test01/config.json` o `implementation/config.json` (lo script li rileva automaticamente).
3. Oppure imposta le variabili d'ambiente:
   ```bash
   export ETRANSLATION_USERNAME="il-tuo-username"
   export ETRANSLATION_PASSWORD="la-tua-password"
   ```

Esegui lo script:

```bash
python3 APITesting/test02/run_test.py
```

Opzioni disponibili:
- `--callback-url <URL>`: Specifica un URL HTTP per ricevere il callback di successo con il testo tradotto.
- `--text "<testo>"`: Modifica il testo da tradurre (default: `"Validator of turtle files (.ttl)"`). Se vuoi testare esplicitamente la stringa italiana come input per l'engine EN, puoi passare `--text "Turtle (.ttl) file validator"`.
- `--source <LANG>`: Lingua sorgente (default: `EN`).
- `--targets <LANG ...>`: Lingue destinazione (default: `IT DE`).
- `--glossary <path>`: Percorso personalizzato del file glossario.
