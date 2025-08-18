from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
from datetime import datetime, date
from django.db.models import Sum, Count, Q
from decimal import Decimal


class AnneeScolaire(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee_debut = models.IntegerField()  
    annee_fin = models.IntegerField()   
    date_debut = models.DateField()      
    date_fin = models.DateField()        
    est_active = models.BooleanField(default=False)  
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-annee_debut']
        unique_together = ['annee_debut', 'annee_fin']

    def __str__(self):
        return f"{self.annee_debut}-{self.annee_fin}"

    @property
    def libelle(self):
        return f"Année scolaire {self.annee_debut}-{self.annee_fin}"

    @classmethod
    def get_annee_courante(cls):
        return cls.objects.filter(est_active=True).first()

    @classmethod
    def get_annee_pour_date(cls, date_donnee):
        return cls.objects.filter(
            date_debut__lte=date_donnee,
            date_fin__gte=date_donnee
        ).first()

    @classmethod
    def creer_annee_scolaire(cls, annee_debut):
        annee_fin = annee_debut + 1
        date_debut = date(annee_debut, 7, 1) 
        date_fin = date(annee_fin, 6, 30)   
        
        return cls.objects.create(
            annee_debut=annee_debut,
            annee_fin=annee_fin,
            date_debut=date_debut,
            date_fin=date_fin
        )

    def activer(self):
        AnneeScolaire.objects.all().update(est_active=False)
        self.est_active = True
        self.save()

    def get_mois_scolaires(self):
        mois = []
        current_date = self.date_debut
        
        while current_date <= self.date_fin:
            mois.append({
                'numero': current_date.month,
                'annee': current_date.year,
                'nom': current_date.strftime('%B %Y'),
                'nom_court': current_date.strftime('%m/%Y'),
                'date_debut': date(current_date.year, current_date.month, 1),
                'date_fin': date(
                    current_date.year + (1 if current_date.month == 12 else 0),
                    1 if current_date.month == 12 else current_date.month + 1,
                    1
                ) - timezone.timedelta(days=1)
            })
            
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
                
        return mois


class Cahiers(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.TextField()
    prix = models.DecimalField(max_digits=10, decimal_places=2)  # CORRECTION: Decimal au lieu d'Integer
    quantite_stock = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titre


class Ecoles(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.TextField()
    adresse = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nom


class Vente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ecole = models.ForeignKey(Ecoles, on_delete=models.CASCADE, related_name='ventes')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='ventes')
    date_paiement = models.DateTimeField(null=True, blank=True) 
    facture_pdf = models.FileField(upload_to='factures/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    modified_at = models.DateTimeField(null=True, blank=True)
    derniere_modification_type = models.CharField(max_length=50, null=True, blank=True) 
    articles_ajoutes_session = models.TextField(null=True, blank=True)
    dette_precedente = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Dette des années précédentes")
    description_dette = models.TextField(blank=True, null=True, help_text="Description de la dette (ex: 'Reliquat année 2023-2024')")
    
    def enregistrer_ajout_articles(self, nouveaux_articles):
        import json
        from django.utils import timezone
        
        self.modified_at = timezone.now()
        self.derniere_modification_type = 'ajout'
        
        articles_data = []
        for article in nouveaux_articles:
            articles_data.append({
                'cahier_titre': article['cahier'].titre,
                'quantite': article['quantite'],
                'prix_unitaire': float(article['cahier'].prix),  # CORRECTION: conversion en float
                'total': article['quantite'] * float(article['cahier'].prix)  # CORRECTION: conversion en float
            })
        
        self.articles_ajoutes_session = json.dumps(articles_data)
        self.save()
    
    def get_articles_ajoutes_derniere_session(self):
        if self.articles_ajoutes_session:
            import json
            try:
                return json.loads(self.articles_ajoutes_session)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def get_lignes_originales(self):
        """Retourne les lignes originales (exclut les ajouts récents si c'est un ajout)"""
        if not self.modified_at or self.derniere_modification_type != 'ajout':
            return self.lignes.all()
        
        articles_ajoutes = self.get_articles_ajoutes_derniere_session()
        if not articles_ajoutes:
            return self.lignes.all()
        
        articles_ajoutes_titres = [article['cahier_titre'] for article in articles_ajoutes]
        
        lignes_originales = []
        lignes_ajoutees_ids = set()
        
        # Identifier d'abord les lignes ajoutées (les plus récentes par titre)
        for titre in articles_ajoutes_titres:
            ligne_recente = self.lignes.filter(cahier__titre=titre).order_by('-id').first()
            if ligne_recente:
                lignes_ajoutees_ids.add(ligne_recente.id)
        
        # Retourner toutes les autres lignes
        for ligne in self.lignes.all().order_by('id'):
            if ligne.id not in lignes_ajoutees_ids:
                lignes_originales.append(ligne)
        
        return lignes_originales
    
    def get_lignes_ajoutees_recemment(self):
        """Retourne les lignes ajoutées lors de la dernière modification"""
        if not self.modified_at or self.derniere_modification_type != 'ajout':
            return []
        
        articles_ajoutes = self.get_articles_ajoutes_derniere_session()
        if not articles_ajoutes:
            return []
        
        lignes_ajoutees = []
        articles_ajoutes_titres = [article['cahier_titre'] for article in articles_ajoutes]
        
        # Pour chaque titre d'article ajouté, récupérer la ligne la plus récente
        for titre in articles_ajoutes_titres:
            ligne_recente = self.lignes.filter(cahier__titre=titre).order_by('-id').first()
            if ligne_recente:
                lignes_ajoutees.append(ligne_recente)
        
        return lignes_ajoutees
    
    @property
    def montant_total_articles(self):
        """Montant total des articles uniquement (sans dette précédente)"""
        return sum(Decimal(str(ligne.montant)) for ligne in self.lignes.all())
    
    @property
    def montant_total(self):
        """Montant total = articles + dette précédente"""
        return self.montant_total_articles + (self.dette_precedente or Decimal('0'))
    
    @property
    def montant_paye(self):
        """Montant total payé"""
        return sum(p.montant for p in self.paiements.all())
    
    def montant_restant(self):
        """Montant restant à payer"""
        return max(self.montant_total - self.montant_paye, Decimal('0'))
    
    def est_reglee(self):
        """Vérifier si la vente est entièrement réglée"""
        return self.montant_restant() <= Decimal('0')

    def save(self, *args, **kwargs):
        if not self.annee_scolaire:
            # Utiliser la date de création si disponible, sinon maintenant
            date_ref = self.created_at.date() if self.created_at else timezone.now().date()
            self.annee_scolaire = AnneeScolaire.get_annee_pour_date(date_ref) or AnneeScolaire.get_annee_courante()
        super().save(*args, **kwargs)

    def nombre_tranches_payees(self):
        """Nombre de tranches déjà payées"""
        return self.paiements.count()
    
    def peut_ajouter_tranche(self):
        """Vérifier si on peut ajouter une tranche de paiement"""
        return self.nombre_tranches_payees() < 3 and not self.est_reglee()
    
    def est_en_retard(self): 
        """Vérifier si la vente est en retard de paiement"""
        if self.date_paiement and not self.est_reglee():
            return timezone.now() > self.date_paiement
        return False
    
    def statut_paiement(self):
        """Retourne le statut de paiement"""
        if self.est_reglee():
            return "Réglée"
        elif self.est_en_retard():
            return "En retard"
        else:
            return "En cours"

    def __str__(self):
        date_str = self.date_paiement.strftime('%d/%m/%Y') if self.date_paiement else 'Date inconnue'
        return f"Vente à {self.ecole.nom} le {date_str} ({self.annee_scolaire})"


class Paiement(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name='paiements')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_paiement = models.DateField(auto_now_add=True)
    numero_tranche = models.IntegerField(default=1)

    class Meta:
        ordering = ['numero_tranche']

    def __str__(self):
        return f"{self.vente.ecole.nom} - Tranche {self.numero_tranche} - {self.montant} F le {self.date_paiement}"


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name='lignes')
    cahier = models.ForeignKey(Cahiers, on_delete=models.CASCADE)
    quantite = models.IntegerField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)  # CORRECTION: Decimal au lieu d'Integer

    def save(self, *args, **kwargs):
        # CORRECTION: Calcul correct avec Decimal
        self.montant = Decimal(str(self.quantite)) * self.cahier.prix
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantite} x {self.cahier.titre} pour {self.vente.ecole.nom}"


class BilanAnneeScolaire(models.Model):
    """Bilan annuel d'une année scolaire"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee_scolaire = models.OneToOneField(AnneeScolaire, on_delete=models.CASCADE, related_name='bilan')
    
    # Métriques globales
    nombre_ventes_total = models.IntegerField(default=0)
    montant_total_ventes = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    montant_total_paye = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    montant_total_impaye = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Métriques par cahier (JSON)
    ventes_par_cahier = models.JSONField(default=dict)  # {cahier_id: {titre, quantite_vendue, ca_genere}}
    
    # Métriques par école
    nombre_ecoles_actives = models.IntegerField(default=0)
    
    date_generation = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Bilan {self.annee_scolaire}"

    @classmethod
    def generer_bilan(cls, annee_scolaire):
        """Génère ou met à jour le bilan pour une année scolaire"""
        bilan, created = cls.objects.get_or_create(annee_scolaire=annee_scolaire)
        
        # Récupération des ventes de l'année
        ventes = Vente.objects.filter(annee_scolaire=annee_scolaire)
        
        # Calculs globaux
        bilan.nombre_ventes_total = ventes.count()
        bilan.montant_total_ventes = sum(v.montant_total for v in ventes)
        bilan.montant_total_paye = sum(v.montant_paye for v in ventes)
        bilan.montant_total_impaye = bilan.montant_total_ventes - bilan.montant_total_paye
        
        # Nombre d'écoles actives
        bilan.nombre_ecoles_actives = ventes.values('ecole').distinct().count()
        
        # Analyse par cahier
        ventes_par_cahier = {}
        cahiers = Cahiers.objects.all()
        
        for cahier in cahiers:
            lignes_cahier = LigneVente.objects.filter(
                vente__annee_scolaire=annee_scolaire,
                cahier=cahier
            )
            
            quantite_vendue = sum(ligne.quantite for ligne in lignes_cahier)
            ca_genere = sum(ligne.montant for ligne in lignes_cahier)
            
            ventes_par_cahier[str(cahier.id)] = {
                'titre': cahier.titre,
                'prix_unitaire': float(cahier.prix),
                'quantite_vendue': quantite_vendue,
                'ca_genere': float(ca_genere),
                'stock_actuel': cahier.quantite_stock
            }
        
        bilan.ventes_par_cahier = ventes_par_cahier
        bilan.save()
        
        return bilan


class BilanMensuel(models.Model):
    """Bilan mensuel d'une année scolaire"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='bilans_mensuels')
    mois = models.IntegerField()  # 1-12
    annee = models.IntegerField()  # 2024, 2025, etc.
    
    # Métriques du mois
    nombre_ventes = models.IntegerField(default=0)
    montant_ventes = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    montant_paye = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Détail par cahier
    ventes_par_cahier = models.JSONField(default=dict)
    
    date_generation = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['annee_scolaire', 'mois', 'annee']
        ordering = ['annee', 'mois']

    def __str__(self):
        return f"Bilan {self.mois:02d}/{self.annee} - {self.annee_scolaire}"

    @property
    def nom_mois(self):
        mois_noms = [
            '', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
            'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
        ]
        return mois_noms[self.mois]

    @classmethod
    def generer_bilan_mois(cls, annee_scolaire, mois, annee):
        """Génère le bilan pour un mois donné"""
        bilan, created = cls.objects.get_or_create(
            annee_scolaire=annee_scolaire,
            mois=mois,
            annee=annee
        )
        
        # Dates de début et fin du mois
        debut_mois = date(annee, mois, 1)
        if mois == 12:
            fin_mois = date(annee + 1, 1, 1) - timezone.timedelta(days=1)
        else:
            fin_mois = date(annee, mois + 1, 1) - timezone.timedelta(days=1)
        
        # Ventes du mois
        ventes_mois = Vente.objects.filter(
            annee_scolaire=annee_scolaire,
            created_at__date__range=[debut_mois, fin_mois]
        )
        
        # Paiements du mois
        paiements_mois = Paiement.objects.filter(
            vente__annee_scolaire=annee_scolaire,
            date_paiement__range=[debut_mois, fin_mois]
        )
        
        # Calculs
        bilan.nombre_ventes = ventes_mois.count()
        bilan.montant_ventes = sum(v.montant_total for v in ventes_mois)
        bilan.montant_paye = sum(p.montant for p in paiements_mois)
        
        # Analyse par cahier pour le mois
        ventes_par_cahier = {}
        cahiers = Cahiers.objects.all()
        
        for cahier in cahiers:
            lignes_mois = LigneVente.objects.filter(
                vente__in=ventes_mois,
                cahier=cahier
            )
            
            quantite_vendue = sum(ligne.quantite for ligne in lignes_mois)
            ca_genere = sum(ligne.montant for ligne in lignes_mois)
            
            if quantite_vendue > 0:  
                ventes_par_cahier[str(cahier.id)] = {
                    'titre': cahier.titre,
                    'prix_unitaire': float(cahier.prix),            
                    'quantite_vendue': quantite_vendue,
                    'ca_genere': float(ca_genere),
                    'stock_actuel': cahier.quantite_stock      
                }
        
        bilan.ventes_par_cahier = ventes_par_cahier
        bilan.save()
        
        return bilan

    @classmethod
    def generer_tous_bilans_mensuels(cls, annee_scolaire):
        """Génère tous les bilans mensuels pour une année scolaire"""
        mois_scolaires = annee_scolaire.get_mois_scolaires()
        bilans = []
        
        for mois_info in mois_scolaires:
            bilan = cls.generer_bilan_mois(
                annee_scolaire,
                mois_info['numero'],
                mois_info['annee']
            )
            bilans.append(bilan)
        
        return bilans