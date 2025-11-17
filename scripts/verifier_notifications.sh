#!/bin/bash

# Script pour exécuter la vérification des notifications
# Ce script doit être exécuté deux fois par jour via cron

# Naviguer vers le répertoire du projet
cd /Applications/XAMPP/xamppfiles/htdocs/Projects/MD/Cahier_ecriture

# Activer l'environnement virtuel et exécuter la commande
source .venv/bin/activate
python manage.py verifier_notifications

# Log de la date d'exécution
echo "$(date): Vérification des notifications exécutée" >> /var/log/cahier_notifications.log