# Esporre il callback server con GitHub Codespaces

Questa guida spiega come avviare il callback server in un codespace di GitHub e renderlo raggiungibile via HTTPS dall'API eTranslation.

> Il codespace è un ambiente di sviluppo: si ferma dopo circa 30 minuti di inattività e l'URL pubblico cambia a ogni nuovo codespace. Per un servizio stabile usa una piattaforma di hosting.

## Attività su GitHub

### 1. Crea il codespace

1. Apri il repository `vintra73/eTranslationTest` su GitHub.
2. Clicca **Code → Codespaces → Create codespace on main**.
3. Attendi che l'ambiente sia pronto. Il container include Python 3.

### 2. Avvia il server

Nel terminale del codespace:

```bash
cd client/codespaces
bash start_callback_server.sh
```

Il server ascolta su `0.0.0.0:8000`, con i path definiti in `client/callback_server.json`:

- `/etranslation/success`
- `/etranslation/failure`
- `/etranslation/delivery`

Lascia il terminale aperto: chiudendolo il server si ferma.

### 3. Rendi la porta pubblica

1. Apri il pannello **Ports** (scheda in basso accanto al terminale). Se non lo vedi, usa **View → Ports** oppure il comando *Ports: Focus on Ports View*.
2. Trova la riga con la porta **8000**. Se non compare, aggiungila con **Forward a Port** e scrivi `8000`.
3. Clicca con il tasto destro sulla riga, scegli **Port Visibility → Public**.

Questo passaggio è obbligatorio: con la porta *Private* le callback di eTranslation ricevono una pagina di login di GitHub e non arrivano al server.

### 4. Copia l'URL pubblico

Nella stessa riga della porta 8000, copia l'indirizzo nella colonna **Forwarded Address**. Ha questa forma:

```
https://<nome-codespace>-8000.app.github.dev
```

### 5. Verifica il server

Da un terminale locale:

```bash
curl -i -X POST https://<nome-codespace>-8000.app.github.dev/altro
```

Deve rispondere `404`, cioè il server è raggiungibile. Il server accetta solo richieste `POST`: una `GET` restituisce `501`, comportamento normale.

### 6. Usa l'URL nelle richieste del client

Nel codice che invia le richieste a eTranslation, usa come base l'URL copiato:

```python
BASE = "https://<nome-codespace>-8000.app.github.dev"

notifications = {
    "success": {"http": f"{BASE}/etranslation/success"},
    "failure": {"http": f"{BASE}/etranslation/failure"},
}
deliveries = {"http": f"{BASE}/etranslation/delivery"}
```

Ogni volta che il codespace viene riavviato o ricreato, l'URL cambia. Aggiorna i riferimenti nelle richieste successive.

## Note

- Il server non ha autenticazione. Chiunque conosca l'URL può inviare callback finte.
- Per consultare le callback ricevute guarda l'output del terminale dove gira il server.
- Il piano gratuito di Codespaces ha un numero limitato di ore di core al mese. Ferma il codespace quando non lo usi da **Codespaces → Stop current codespace** nella pagina github.com/codespaces.
