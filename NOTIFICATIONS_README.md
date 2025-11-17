# Configuration du système de notifications - Cahier Écriture

## Configuration des emails

1. **Configurer le serveur SMTP dans settings.py :**
   ```python
   EMAIL_HOST_USER = 'votre-email@gmail.com'
   EMAIL_HOST_PASSWORD = 'votre-mot-de-passe-application'
   ```

2. **Ajouter des emails de notification :**
   - Aller sur la page Notifications
   - Cliquer sur "Gérer les emails"
   - Ajouter les adresses emails qui doivent recevoir les notifications

## Système d'envoi en temps réel

Le système vérifie automatiquement les notifications et envoie les emails à chaque chargement des pages principales :
- Page d'accueil (dashboard)
- Page des notifications
- Page de gestion des cahiers
- Page des ventes

Cette approche garantit une réactivité immédiate sans configuration de tâches cron.

### Test manuel via l'interface
- Aller sur `/notifications/test/` pour déclencher manuellement la vérification

## Fonctionnalités disponibles

1. **Notifications de stock faible** (≤ 100)
2. **Interface de gestion des notifications** avec :
   - Liste paginée avec filtres
   - Suppression individuelle
   - Marquage comme lu
   - Statistiques

3. **Gestion des emails** :
   - Ajout/suppression d'emails
   - Activation/désactivation
   - Test d'envoi

## Tests

1. Créer un cahier avec un stock ≤ 100
2. Naviguer vers n'importe quelle page principale (accueil, cahiers, ventes)
3. Les notifications sont automatiquement vérifiées et les emails envoyés
4. Vérifier que la notification apparaît dans la liste
5. Vérifier la réception de l'email (si configuré)

## Seuil de stock

Le seuil par défaut est 100. Pour le modifier, changer la valeur dans settings.py :
```python
NOTIFICATION_SEUIL_STOCK = 50  # Nouveau seuil
```

## Performance

Le système inclut une gestion d'erreur pour éviter d'interrompre le chargement des pages en cas de problème avec l'envoi d'emails.