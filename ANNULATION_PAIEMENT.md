# Fonctionnalité d'annulation de paiement

## 📋 Description

Cette fonctionnalité permet d'annuler un paiement déjà enregistré sur une vente. **Important :** Le paiement n'est pas supprimé mais marqué comme annulé, conservant ainsi l'historique complet des transactions. Cette approche est conforme aux bonnes pratiques comptables.

## ✨ Fonctionnalités

### 1. **Bouton d'annulation**
- Un bouton avec une icône de croix rouge est affiché à côté de chaque paiement non annulé
- Survol du bouton pour voir l'info-bulle "Annuler ce paiement"
- Les paiements annulés affichent simplement "Annulé" sans bouton d'action

### 2. **Confirmation de sécurité**
- Un message de confirmation s'affiche avant l'annulation
- Affiche le numéro de tranche et le montant à annuler
- Avertissement que les calculs seront mis à jour mais l'historique conservé

### 3. **Processus d'annulation**
Lorsqu'un paiement est annulé :
- ✅ Le paiement est marqué comme annulé (`est_annule = True`)
- ✅ La date d'annulation est enregistrée
- ✅ Le paiement reste visible dans l'historique avec un style différent
- ✅ Les calculs de montant payé et restant excluent automatiquement les paiements annulés
- ✅ Un message de succès confirme l'annulation
- ✅ La page est rechargée automatiquement pour afficher les changements

### 4. **Affichage visuel des paiements annulés**
Les paiements annulés sont facilement identifiables :
- 🎨 Affichés avec une opacité réduite (60%)
- 🎨 Texte barré pour indication visuelle claire
- 🎨 Icône "cancel" au lieu de "calendar_today"
- 🎨 Badge gris avec mention "ANNULÉ"
- 🎨 Date d'annulation affichée en rouge sous la date du paiement
- 🎨 Montant affiché en gris au lieu de vert

## 🔧 Implémentation technique

### Modifications de la base de données
Nouveaux champs ajoutés au modèle `Paiement` :
```python
est_annule = models.BooleanField(default=False)
date_annulation = models.DateTimeField(null=True, blank=True)
```

### Backend (`gestion/Views/sales.py`)
```python
@require_POST
def annuler_paiement(request, vente_id, paiement_id):
    """Marquer un paiement comme annulé (sans le supprimer pour garder l'historique)"""
```

**Calculs mis à jour :**
Tous les calculs de montants payés excluent automatiquement les paiements annulés :
- `liste_ventes` : Calcul du montant restant par vente
- `ventes_ajax` : Données AJAX pour les ventes
- `vente_detail` : Page de détail de vente
- `gerer_paiement` : Gestion des nouveaux paiements

### Génération de PDF (`gestion/views_pdf.py`)
Les factures PDF excluent également les paiements annulés :
```python
paiements_vente = vente.paiements.filter(est_annule=False).order_by('date_paiement')
```

### URL (`gestion/urls.py`)
```python
path('ventes/<uuid:vente_id>/paiement/<int:paiement_id>/annuler/', annuler_paiement, name='annuler_paiement')
```

### Frontend (`templates/vente_detail.html`)
- Bouton d'annulation avec icône Material Symbols
- Style conditionnel pour paiements annulés
- Script JavaScript pour gérer la requête AJAX
- Confirmation utilisateur avant action

## 🎯 Utilisation

1. Accéder à la page de détail d'une vente
2. Localiser la section "Historique des paiements"
3. Cliquer sur l'icône de croix rouge à côté du paiement à annuler
4. Confirmer l'action dans la boîte de dialogue
5. La page se recharge automatiquement avec les modifications

## ⚠️ Points d'attention

- **Historique préservé** : Les paiements annulés restent visibles dans l'historique
- **Calculs automatiques** : Le montant restant et montant payé sont recalculés automatiquement
- **Double annulation** : Impossible d'annuler un paiement déjà annulé
- **Factures PDF** : Les factures générées excluent automatiquement les paiements annulés
- **Audit trail** : Date d'annulation enregistrée pour traçabilité

## 🔄 Cas d'usage

### Cas 1 : Paiement erroné
Un paiement a été enregistré par erreur avec un mauvais montant ou pour la mauvaise vente.
→ Annuler le paiement et en créer un nouveau correct. L'historique montre les deux opérations.

### Cas 2 : Annulation de transaction
Un paiement initialement accepté a été refusé par la banque ou annulé par le client.
→ Annuler le paiement pour refléter la situation réelle tout en gardant la trace de la tentative.

### Cas 3 : Correction de saisie
Un montant incorrect a été saisi.
→ Annuler le paiement erroné et créer un nouveau paiement avec le bon montant.

### Cas 4 : Audit et traçabilité
Besoin de vérifier l'historique complet des paiements y compris les annulations.
→ Tous les paiements annulés sont visibles avec leur date d'annulation.

## 🛡️ Sécurité

- **Authentification requise** : L'utilisateur doit être connecté
- **Méthode POST uniquement** : Empêche l'annulation par URL directe
- **CSRF protection** : Token CSRF vérifié sur chaque requête
- **Vérification d'existence** : Vérifie que le paiement appartient bien à la vente
- **Confirmation utilisateur** : Double vérification avant action
- **Protection contre double annulation** : Vérification que le paiement n'est pas déjà annulé

## 📊 Impact sur les données

### Données modifiées :
- **Paiement.est_annule** : Passe à `True`
- **Paiement.date_annulation** : Enregistre la date et heure d'annulation
- **Montant restant** : Recalculé automatiquement (propriété calculée)
- **Montant payé** : Recalculé en excluant les paiements annulés

### Données conservées :
- **Paiement** : Reste dans la base de données
- **Montant original** : Conservé tel quel
- **Date de paiement** : Conservée
- **Numéro de tranche** : Conservé
- **Lignes de vente** : Restent inchangées
- **Stock des cahiers** : Non modifié

### Impact sur les calculs :
Tous les endroits où les montants sont calculés excluent automatiquement les paiements annulés :
- ✅ Liste des ventes
- ✅ Détail de vente
- ✅ Calcul des dettes
- ✅ Génération de factures PDF
- ✅ Statistiques et rapports

## 🔍 Traçabilité

### Informations enregistrées :
1. **État original** : Le paiement garde toutes ses informations d'origine
2. **Marqueur d'annulation** : `est_annule = True`
3. **Horodatage** : Date et heure exactes de l'annulation
4. **Affichage** : Les paiements annulés restent visibles dans l'interface

### Avantages de cette approche :
- 📝 **Conformité comptable** : Respecte les normes d'audit
- 🔒 **Intégrité des données** : Aucune donnée perdue
- 📊 **Analyse possible** : Peut analyser les tendances d'annulation
- ⚖️ **Responsabilité** : Historique complet traçable
- 🔍 **Transparence** : Toutes les transactions visibles

## 🚀 Améliorations futures possibles

1. **Raison d'annulation** : Ajouter un champ pour documenter la raison
2. **Utilisateur** : Enregistrer qui a effectué l'annulation
3. **Restauration** : Permettre de "dé-annuler" un paiement dans un délai limité
4. **Notification** : Envoyer une notification par email lors de l'annulation
5. **Rapport d'audit** : Vue dédiée pour analyser les paiements annulés
6. **Export** : Exporter l'historique complet incluant les annulations
7. **Statistiques** : Tableau de bord des taux d'annulation par période/école

## 📝 Migration de base de données

Migration créée : `0009_paiement_date_annulation_paiement_est_annule.py`

Commandes exécutées :
```bash
python manage.py makemigrations
python manage.py migrate
```

Les paiements existants ont automatiquement `est_annule=False` et `date_annulation=NULL`.
