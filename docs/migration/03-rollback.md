# Návrat zpět (rollback)

Migrace je stavěná tak, aby šla kdykoliv vzít zpět. Existují dvě nezávislé
úrovně — obvykle stačí ta první.

---

## Úroveň 1 — vrátit provoz na Railway (řádově sekundy)

Tohle je ten důležitý scénář: bot na VPS zlobí a potřebuješ, aby zase fungoval.

**Předpoklad:** služba na Railway nebyla smazaná. Proto se maže až po několika
dnech bezproblémového provozu na VPS.

O tom, kam Telegram doručuje zprávy, rozhoduje jediné volání `setWebhook`.
Návrat je tedy přeregistrování zpět na Railway:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<railway-domena>/webhook"
```

Když je nastavený `WEBHOOK_SECRET`, přidej ho:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<railway-domena>/webhook&secret_token=<SECRET>"
```

Pak zastav službu na VPS, aby si webhook nevzala zpátky při restartu:

```bash
systemctl stop fbig-bot
systemctl disable fbig-bot
```

Ověření:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Bot na Railway začne odpovídat okamžitě.

### Proč se tím nic neztratí

Ve Fázi A se **nemigrují žádná data**. Obě instance — Railway i VPS — čtou
a zapisují do stejného Google Sheetu. Ať běží kterákoliv, data jsou stejná
a kompletní.

### Jedno pravidlo

Webhook smí mít registrovaný **jen jedna instance**. Telegram doručuje vždy
na naposledy nastavenou adresu, takže se instance nemůžou „přetahovat" —
ale znamená to, že po přepnutí zpět je nutné službu na VPS opravdu zastavit.
Jinak by si při příštím restartu (`Restart=always`) webhook vzala zpět, protože
si ho registruje sama při startu podle `PUBLIC_URL`.

Alternativa bez zastavování služby: vymazat `PUBLIC_URL` v `/opt/fbig-bot/.env`
a restartovat. Bot pak běží, ale webhook si nenárokuje.

---

## Úroveň 2 — vrátit změny v kódu

Změny v repu jsou záměrně minimální a téměř výhradně aditivní: nové soubory
v `deploy/` a `docs/`, plus **jediný upravený řádek** v `main.py` (adresa,
na které aplikace poslouchá, se čte z proměnné `HOST` s výchozí hodnotou
`0.0.0.0` — tedy stejné chování jako předtím, když se `HOST` nenastaví).

### Před mergem do `main`

Označ si výchozí stav, ať je kam se vrátit:

```bash
git checkout main
git pull
git tag pre-railway-migration
git push origin pre-railway-migration
```

### Po mergnutí — vrácení

Pokud byl PR mergnutý přes **Squash and merge**, je celá migrace jeden commit:

- na GitHubu tlačítko **Revert** u mergnutého PR, nebo
- lokálně:

```bash
git checkout main
git pull
git revert <sha-merge-commitu>
git push
```

Nouzový návrat na označený stav:

```bash
git reset --hard pre-railway-migration
```

(Přepisuje historii — používej jen když víš, že o mezitím vzniklé commity
nepřijdeš.)

---

## Rollback Fáze B (až bude nasazená)

Fáze B přenáší data do Supabase. I tam zůstává cesta zpět:

- **Google Sheets se nemaže** — zůstává jako živá záloha, jen se do něj
  přestane zapisovat.
- Návrat = v `main.py` vrátit import z `db` zpět na `sheets` a restartovat.
- Data zapsaná do Supabase po přepnutí by se do Sheets musela dopsat ručně
  (nebo obráceným během migračního skriptu) — proto se rollback Fáze B vyplatí
  udělat brzy, ne po měsíci provozu.
