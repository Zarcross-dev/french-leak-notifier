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

## 📦 Installation

```bash
pip install -r requirements.txt
```

## ⚙️ Configuration

Éditez le fichier `config.json` :

```json
{
    "webhook_url": "https://discord.com/api/webhooks/VOTRE_ID/VOTRE_TOKEN",
    "notification_mode": "realtime",
    "check_interval_seconds": 300
}
```

| Paramètre | Description |
|---|---|
| `webhook_url` | URL du webhook Discord |
| `notification_mode` | `realtime`, `1d`, `7d` ou `30d` |
| `check_interval_seconds` | Intervalle de vérification en secondes (mode realtime uniquement, défaut 300 = 5 min) |

## 🚀 Lancement

```bash
python main.py
```

Le programme tourne en continu. Lors de la première exécution, il indexe toutes les fuites existantes sans envoyer de notification. Seules les **nouvelles** fuites détectées seront envoyées.

## 📁 Fichiers

| Fichier | Description |
|---|---|
| `main.py` | Programme principal |
| `config.json` | Configuration (webhook, mode, intervalle) |
| `seen_leaks.json` | Base des fuites déjà vues (généré automatiquement) |
| `requirements.txt` | Dépendances Python |

## 📸 Aperçu Discord

Chaque notification contient :
- Le nom de l'organisme touché
- La véracité du leak (couleur de l'embed)
- Le nombre de personnes affectées
- La liste des données exposées
- Les liens vers les sources
