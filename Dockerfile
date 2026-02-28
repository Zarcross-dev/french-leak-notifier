FROM python:3.12-slim

LABEL maintainer="Zarcross-dev"
LABEL description="French Leak Notifier - Surveille les fuites de données françaises"

# Empêcher Python de bufferiser stdout/stderr (logs en temps réel)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Répertoire de données persistantes
ENV DATA_DIR=/app/data

WORKDIR /app

# Copier et installer les dépendances d'abord (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Créer un utilisateur non-root + dossier de données
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

# Copier le code source
COPY --chown=appuser:appuser main.py .

# Volume pour persister les leaks déjà vus entre les redémarrages
VOLUME ["/app/data"]

USER appuser

CMD ["python", "main.py"]
