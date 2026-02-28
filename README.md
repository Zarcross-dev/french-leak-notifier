# 🇫🇷 French Leak Notifier

Surveillez les fuites de données françaises en temps réel ! Ce programme parse le site [bonjourlafuite.eu.org](https://bonjourlafuite.eu.org/) et envoie les nouvelles fuites sur un webhook Discord avec des embeds colorés selon la véracité.

## 🎯 Fonctionnalités

- **Parsing automatique** du site bonjourlafuite.eu.org
- **4 modes de notification** :
  - `realtime` — Vérifie régulièrement et envoie chaque nouveau leak immédiatement
  - `1d` — Récapitulatif quotidien (fuites des dernières 24h)
  - `7d` — Récapitulatif hebdomadaire
  - `30d` — Récapitulatif mensuel
- **Embeds Discord colorés** selon la véracité :
  - 🟢 Vert — Confirmée
  - 🟠 Orange — Revendiquée (crédible)
  - 🔴 Rouge — Revendiquée (peu fiable)
- **Données complètes** : nom, données exposées, nombre de personnes affectées, sources
- **Dédoublonnage** automatique (ne renvoie jamais deux fois la même fuite)
- **Docker** — Déploiement simple avec Docker Compose

---

## � Docker (recommandé)

### Démarrage rapide

```bash
# 1. Cloner le dépôt
git clone https://github.com/Zarcross-dev/french-leak-notifier.git
cd french-leak-notifier

# 2. Configurer les variables d'environnement
cp .env.example .env
# Éditez .env et renseignez votre WEBHOOK_URL

# 3. Lancer
docker compose up -d
```

### Variables d'environnement

| Variable | Obligatoire | Défaut | Description |
|---|---|---|---|
| `WEBHOOK_URL` | ✅ | — | URL du webhook Discord |
| `NOTIFICATION_MODE` | ❌ | `realtime` | `realtime`, `1d`, `7d` ou `30d` |
| `CHECK_INTERVAL` | ❌ | `300` | Intervalle de vérification en secondes (mode realtime) |

### Commandes utiles

```bash
# Voir les logs en temps réel
docker compose logs -f

# Redémarrer après changement de config
docker compose down && docker compose up -d

# Rebuild après mise à jour du code
docker compose up -d --build
```

### Persistance des données

Les leaks déjà vus sont stockés dans un volume Docker (`leak-data`). Les données persistent entre les redémarrages du conteneur.

---

## �📦 Installation locale (sans Docker)

```bash
pip install -r requirements.txt
```

### ⚙️ Configuration

Vous pouvez configurer via **variables d'environnement** ou via le fichier `config.json` :

#### Option 1 : Variables d'environnement

```bash
export WEBHOOK_URL="https://discord.com/api/webhooks/VOTRE_ID/VOTRE_TOKEN"
export NOTIFICATION_MODE="realtime"
export CHECK_INTERVAL="300"
python main.py
```

#### Option 2 : Fichier config.json

```json
{
    "webhook_url": "https://discord.com/api/webhooks/VOTRE_ID/VOTRE_TOKEN",
    "notification_mode": "realtime",
    "check_interval_seconds": 300
}
```

> **Note :** Les variables d'environnement sont prioritaires sur `config.json`.

### 🚀 Lancement

```bash
python main.py
```

Le programme tourne en continu. Lors de la première exécution, il indexe toutes les fuites existantes sans envoyer de notification. Seules les **nouvelles** fuites détectées seront envoyées.

---

## 📁 Fichiers

| Fichier | Description |
|---|---|
| `main.py` | Programme principal |
| `config.json` | Configuration locale (optionnel avec Docker) |
| `seen_leaks.json` | Base des fuites déjà vues (généré automatiquement) |
| `requirements.txt` | Dépendances Python |
| `Dockerfile` | Image Docker |
| `docker-compose.yml` | Orchestration Docker |
| `.env.example` | Template des variables d'environnement |

## 📸 Aperçu Discord

Chaque notification contient :
- Le nom de l'organisme touché
- La véracité du leak (couleur de l'embed)
- Le nombre de personnes affectées
- La liste des données exposées
- Les liens vers les sources
