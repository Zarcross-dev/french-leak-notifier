#!/usr/bin/env python3
"""
French Leak Notifier - Surveille https://bonjourlafuite.eu.org/ et envoie
les nouvelles fuites de donnees sur un webhook Discord.

Modes de notification :
  - realtime : verifie regulierement et envoie chaque nouveau leak des detection
  - 1d       : envoie un recapitulatif quotidien (fuites des dernieres 24 h)
  - 7d       : envoie un recapitulatif hebdomadaire (fuites des 7 derniers jours)
  - 30d      : envoie un recapitulatif mensuel (fuites des 30 derniers jours)
"""

import json
import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
import schedule
from bs4 import BeautifulSoup, Tag

# --------------------------------------------------------------
# Configuration & constants
# --------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR)))
SEEN_PATH = DATA_DIR / "seen_leaks.json"
SITE_URL = "https://bonjourlafuite.eu.org/"

FRENCH_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "f\u00e9vrier": 2, "ao\u00fbt": 8, "d\u00e9cembre": 12,
}

COLOR_GREEN = 0x2ECC71
COLOR_ORANGE = 0xE67E22
COLOR_RED = 0xE74C3C

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("french-leak-notifier")


# --------------------------------------------------------------
# Data structures
# --------------------------------------------------------------

class Leak:
    def __init__(self, name, subtitle, veracity, date, date_raw,
                 affected_count, leaked_data, sources):
        self.name = name
        self.subtitle = subtitle
        self.veracity = veracity
        self.date = date
        self.date_raw = date_raw
        self.affected_count = affected_count
        self.leaked_data = leaked_data
        self.sources = sources

    @property
    def uid(self):
        raw = f"{self.name}|{self.date_raw}".lower().strip()
        return hashlib.md5(raw.encode()).hexdigest()

    @property
    def embed_color(self):
        if self.veracity == "orange":
            return COLOR_ORANGE
        if self.veracity == "red":
            return COLOR_RED
        return COLOR_GREEN

    @property
    def veracity_label(self):
        labels = {
            "green": "\U0001f7e2 Confirmee",
            "orange": "\U0001f7e0 Revendiquee (credible)",
            "red": "\U0001f534 Revendiquee (peu fiable)",
        }
        return labels.get(self.veracity, "? Inconnue")

    def __repr__(self):
        return f"<Leak {self.name!r} ({self.date_raw}) [{self.veracity}]>"


# --------------------------------------------------------------
# Config helpers
# --------------------------------------------------------------

def load_config():
    """
    Charge la configuration depuis les variables d'environnement
    en priorite, puis depuis config.json en fallback.
    Les variables d'environnement supportees :
      - WEBHOOK_URL
      - NOTIFICATION_MODE  (realtime | 1d | 7d | 30d)
      - CHECK_INTERVAL     (en secondes)
    """
    config = {}

    # Fallback : charger config.json s'il existe
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

    # Variables d'environnement (prioritaires)
    env_webhook = os.environ.get("WEBHOOK_URL")
    env_mode = os.environ.get("NOTIFICATION_MODE")
    env_interval = os.environ.get("CHECK_INTERVAL")

    if env_webhook:
        config["webhook_url"] = env_webhook
    if env_mode:
        config["notification_mode"] = env_mode
    if env_interval:
        try:
            config["check_interval_seconds"] = int(env_interval)
        except ValueError:
            log.warning("CHECK_INTERVAL invalide ('%s'), utilisation de la valeur par defaut.", env_interval)

    # Validation minimale
    if not config.get("webhook_url"):
        log.error(
            "Aucune URL de webhook configuree. "
            "Definissez la variable d'environnement WEBHOOK_URL "
            "ou configurez webhook_url dans config.json."
        )
        sys.exit(1)

    return config


def load_seen():
    if not SEEN_PATH.exists():
        return set()
    with open(SEEN_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen(seen):
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


# --------------------------------------------------------------
# Date parsing
# --------------------------------------------------------------

def parse_french_date(text):
    text = text.strip()
    match = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if not match:
        return None
    day, month_str, year = match.groups()
    month = FRENCH_MONTHS.get(month_str.lower())
    if month is None:
        return None
    try:
        return datetime(int(year), month, int(day))
    except ValueError:
        return None


def get_cutoff(days):
    """Return cutoff: start of today minus N days.
    For 1d on 2026-02-28: cutoff = 2026-02-27 00:00:00
    """
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start - timedelta(days=days)


# --------------------------------------------------------------
# Scraping
# --------------------------------------------------------------

def fetch_page():
    try:
        resp = requests.get(SITE_URL, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        log.error("Erreur lors de la recuperation de la page : %s", e)
        return None


def parse_leaks(soup):
    leaks = []
    entries = soup.find_all("div", class_="timeline-description")

    for entry in entries:
        time_tag = entry.find("time")
        date_raw = time_tag.get_text(strip=True) if time_tag else ""
        date_obj = parse_french_date(date_raw) if date_raw else None

        h2 = entry.find("h2")
        if not h2:
            continue
        heading_text = h2.get_text(strip=True)

        if "\U0001f7e2" in heading_text:
            veracity = "green"
        elif "\U0001f7e0" in heading_text:
            veracity = "orange"
        elif "\U0001f534" in heading_text:
            veracity = "red"
        else:
            continue

        name = re.sub(r"[\U0001f7e2\U0001f7e0\U0001f534]", "", heading_text).strip()

        h3 = entry.find("h3")
        subtitle = h3.get_text(strip=True) if h3 else None

        leaked_data = []
        affected_count = None

        p_tag = entry.find("p")
        if p_tag:
            inner_ul = p_tag.find("ul")
            if inner_ul:
                count_parts = []
                for child in p_tag.children:
                    if child == inner_ul:
                        break
                    if isinstance(child, str):
                        text = child.strip()
                        if text:
                            count_parts.append(text)
                    elif isinstance(child, Tag):
                        text = child.get_text(strip=True)
                        if text:
                            count_parts.append(text)
                if count_parts:
                    affected_count = " ".join(count_parts)
                for li in inner_ul.find_all("li", recursive=False):
                    item_text = li.get_text(strip=True)
                    if item_text:
                        leaked_data.append(item_text)
            else:
                p_text = p_tag.get_text(strip=True)
                if p_text:
                    affected_count = p_text

        sources = []
        for ul in entry.find_all("ul", recursive=False):
            if p_tag and ul.parent == p_tag:
                continue
            for li in ul.find_all("li", recursive=False):
                link = li.find("a")
                if link and link.get("href"):
                    href = link["href"]
                    if href.startswith("img/"):
                        href = SITE_URL + href
                    sources.append(href)

        leak = Leak(
            name=name, subtitle=subtitle, veracity=veracity,
            date=date_obj, date_raw=date_raw,
            affected_count=affected_count,
            leaked_data=leaked_data, sources=sources,
        )
        leaks.append(leak)

    return leaks


# --------------------------------------------------------------
# Discord webhook
# --------------------------------------------------------------

def send_discord_embed(webhook_url, leak):
    title = leak.name
    if leak.subtitle:
        title += " \u2014 " + leak.subtitle

    description_parts = []
    description_parts.append(f"**Veracite :** {leak.veracity_label}")
    if leak.affected_count:
        description_parts.append(f"**Personnes affectees :** {leak.affected_count}")
    if leak.date_raw:
        description_parts.append(f"**Date :** {leak.date_raw}")
    description = "\n".join(description_parts)

    fields = []
    if leak.leaked_data:
        data_text = "\n".join(f"\u2022 {item}" for item in leak.leaked_data)
        if len(data_text) > 1024:
            data_text = data_text[:1020] + "\n..."
        fields.append({"name": "\U0001f4cb Donnees exposees", "value": data_text, "inline": False})

    if leak.sources:
        sources_text = "\n".join(
            f"\u2022 [Source {i+1}]({url})" for i, url in enumerate(leak.sources)
        )
        if len(sources_text) > 1024:
            sources_text = sources_text[:1020] + "\n..."
        fields.append({"name": "\U0001f517 Sources", "value": sources_text, "inline": False})

    embed = {
        "title": "\U0001f6a8 " + title,
        "description": description,
        "color": leak.embed_color,
        "fields": fields,
        "footer": {"text": "bonjourlafuite.eu.org"},
        "url": SITE_URL,
    }
    if leak.date:
        embed["timestamp"] = leak.date.isoformat()

    payload = {"embeds": [embed]}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 5)
            log.warning("Rate limited, attente de %ss...", retry_after)
            time.sleep(retry_after + 0.5)
            resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        log.info("Notification envoyee : %s", leak.name)
        return True
    except requests.RequestException as e:
        log.error("Erreur webhook pour %s : %s", leak.name, e)
        return False


def send_discord_summary(webhook_url, leaks, period_label):
    if not leaks:
        return True

    green = [l for l in leaks if l.veracity == "green"]
    orange = [l for l in leaks if l.veracity == "orange"]
    red = [l for l in leaks if l.veracity == "red"]

    desc_parts = [f"**{len(leaks)}** fuite(s) detectee(s) ({period_label})\n"]
    if green:
        desc_parts.append(f"\U0001f7e2 **Confirmees :** {len(green)}")
    if orange:
        desc_parts.append(f"\U0001f7e0 **Revendiquees (credibles) :** {len(orange)}")
    if red:
        desc_parts.append(f"\U0001f534 **Revendiquees (peu fiables) :** {len(red)}")

    description = "\n".join(desc_parts)

    embed = {
        "title": f"\U0001f4ca Recapitulatif des fuites \u2014 {period_label}",
        "description": description,
        "color": COLOR_GREEN,
        "footer": {"text": "bonjourlafuite.eu.org"},
        "url": SITE_URL,
    }
    payload = {"embeds": [embed]}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 5)
            time.sleep(retry_after + 0.5)
            resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        log.info("Recapitulatif envoye (%d fuites)", len(leaks))
    except requests.RequestException as e:
        log.error("Erreur envoi recapitulatif : %s", e)
        return False

    for leak in leaks:
        send_discord_embed(webhook_url, leak)
        time.sleep(1)
    return True


# --------------------------------------------------------------
# Core logic
# --------------------------------------------------------------

def send_startup_preview(config, mode, leaks):
    """Send a preview on startup to verify the bot works."""
    webhook_url = config["webhook_url"]
    log.info("Envoi d'un apercu au demarrage...")

    if not leaks:
        log.warning("   Aucune fuite trouvee pour l'apercu.")
        return

    if mode == "realtime":
        latest = leaks[0]
        log.info("   Apercu : dernier leak -> %s (%s)", latest.name, latest.date_raw)
        send_discord_embed(webhook_url, latest)
    else:
        days_map = {"1d": 1, "7d": 7, "30d": 30}
        days = days_map.get(mode, 1)
        period_labels = {1: "dernieres 24h", 7: "7 derniers jours", 30: "30 derniers jours"}
        period_label = period_labels.get(days, f"{days} derniers jours")
        cutoff = get_cutoff(days)
        log.info("   Cutoff : %s (inclut les fuites depuis cette date)", cutoff)

        recent = [l for l in leaks if l.date and l.date >= cutoff]
        if recent:
            log.info("   Apercu : %d fuite(s) des %s", len(recent), period_label)
            send_discord_summary(webhook_url, recent, period_label)
        else:
            log.info("   Aucune fuite dans les %s pour l'apercu.", period_label)


def check_realtime(config):
    log.info("Verification des nouvelles fuites...")
    webhook_url = config["webhook_url"]
    seen = load_seen()

    soup = fetch_page()
    if soup is None:
        return

    leaks = parse_leaks(soup)
    log.info("%d fuites trouvees sur le site", len(leaks))

    new_leaks = [leak for leak in leaks if leak.uid not in seen]
    if not new_leaks:
        log.info("Aucune nouvelle fuite detectee.")
        return

    log.info("%d nouvelle(s) fuite(s) detectee(s) !", len(new_leaks))
    for leak in new_leaks:
        send_discord_embed(webhook_url, leak)
        seen.add(leak.uid)
        time.sleep(1.5)
    save_seen(seen)


def check_periodic(config, days):
    period_labels = {1: "dernieres 24h", 7: "7 derniers jours", 30: "30 derniers jours"}
    period_label = period_labels.get(days, f"{days} derniers jours")

    log.info("Verification des fuites (%s)...", period_label)
    webhook_url = config["webhook_url"]
    seen = load_seen()

    soup = fetch_page()
    if soup is None:
        return

    leaks = parse_leaks(soup)
    cutoff = get_cutoff(days)
    recent_leaks = [l for l in leaks if l.date and l.date >= cutoff]
    new_leaks = [l for l in recent_leaks if l.uid not in seen]

    if not new_leaks:
        log.info("Aucune nouvelle fuite dans les %s.", period_label)
        return

    log.info("%d nouvelle(s) fuite(s) dans les %s", len(new_leaks), period_label)
    send_discord_summary(webhook_url, new_leaks, period_label)

    for leak in new_leaks:
        seen.add(leak.uid)
    save_seen(seen)


# --------------------------------------------------------------
# Main
# --------------------------------------------------------------

def main():
    config = load_config()
    webhook_url = config.get("webhook_url", "")
    mode = config.get("notification_mode", "realtime")
    check_interval = config.get("check_interval_seconds", 300)

    log.info("=" * 60)
    log.info("French Leak Notifier")
    log.info("   Mode : %s", mode)
    log.info("   Intervalle : %ds", check_interval)
    log.info("   Source : %s", SITE_URL)
    log.info("=" * 60)

    # Fetch once, reuse for indexation + startup preview
    log.info("Recuperation de la page...")
    soup = fetch_page()
    all_leaks = []

    if soup:
        all_leaks = parse_leaks(soup)
        log.info("%d fuites trouvees sur le site", len(all_leaks))
        if not SEEN_PATH.exists():
            log.info("Premiere execution : indexation des fuites existantes...")
            seen = {leak.uid for leak in all_leaks}
            save_seen(seen)
            log.info("   %d fuites indexees.", len(seen))
    else:
        log.warning("Impossible de recuperer la page.")

    # Startup preview
    if all_leaks:
        send_startup_preview(config, mode, all_leaks)

    if mode == "realtime":
        schedule.every(check_interval).seconds.do(check_realtime, config)
    elif mode == "1d":
        schedule.every().day.at("09:00").do(check_periodic, config, 1)
        log.info("Recapitulatif quotidien programme a 09:00")
    elif mode == "7d":
        schedule.every().monday.at("09:00").do(check_periodic, config, 7)
        log.info("Recapitulatif hebdomadaire programme le lundi a 09:00")
    elif mode == "30d":
        schedule.every(30).days.do(check_periodic, config, 30)
        log.info("Recapitulatif mensuel programme tous les 30 jours")
    else:
        log.error("Mode inconnu : %s (supportes : realtime, 1d, 7d, 30d)", mode)
        sys.exit(1)

    log.info("En attente de nouvelles fuites...\n")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("\nArret du programme.")
        sys.exit(0)


if __name__ == "__main__":
    main()
