from django.db import models
from django.db.models import Sum
from django.utils import timezone
import uuid
from datetime import date
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
    
    @property
    def montant_total(self):
        """Montant total de la vente (lignes + dette précédente)"""
        montant_lignes = self.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        dette_precedente = self.dette_precedente or Decimal('0')
        return montant_lignes + dette_precedente
    
    @property
    def montant_paye(self):
        """Montant total payé"""
        return self.paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
    
    @property
    def montant_restant(self):
        """Montant restant à payer"""
        return max(Decimal('0'), self.montant_total - self.montant_paye)

    def get_dettes_par_annee_ecole(self):
        """
        Récupère toutes les dettes de l'école par année scolaire
        Retourne un dictionnaire avec les dettes par année
        """
        # Récupérer toutes les ventes de cette école
        ventes_ecole = Vente.objects.filter(ecole=self.ecole)\
            .select_related('annee_scolaire')\
            .annotate(
                total_lignes=Sum('lignes__montant'),
                total_paye=Sum('paiements__montant')
            )\
            .order_by('-annee_scolaire__annee_debut')
        
        dettes_par_annee = {}
        
        for vente in ventes_ecole:
            annee_str = str(vente.annee_scolaire)
            total_lignes = vente.total_lignes or Decimal('0')
            dette_precedente = vente.dette_precedente or Decimal('0')
            total_vente = total_lignes + dette_precedente
            paye = vente.total_paye or Decimal('0')
            restant = total_vente - paye
            
            if restant > 0:
                if annee_str in dettes_par_annee:
                    dettes_par_annee[annee_str]['montant_restant'] += restant
                    dettes_par_annee[annee_str]['ventes'].append(vente)
                else:
                    dettes_par_annee[annee_str] = {
                        'annee_scolaire': vente.annee_scolaire,
                        'montant_restant': restant,
                        'ventes': [vente],
                        'montant_articles': total_lignes,
                        'dette_precedente': dette_precedente,
                        'montant_total': total_vente,
                        'montant_paye': paye
                    }
        
        return dettes_par_annee
    
    def get_total_dettes_ecole(self):
        """Retourne le montant total des dettes de l'école"""
        dettes = self.get_dettes_par_annee_ecole()
        return sum(dette['montant_restant'] for dette in dettes.values())

    def est_en_retard(self): 
        """Vérifier si la vente est en retard de paiement"""
        return
    
    def statut_paiement(self):
        """Retourne le statut de paiement"""
        return
    
    def get_articles_par_session(self, tolerance_minutes=5):
        """
        Groupe les articles par session d'ajout basé sur la date/heure
        tolerance_minutes: écart maximum en minutes pour considérer les articles comme ajoutés dans la même session
        """
        from datetime import timedelta
        
        lignes = self.lignes.all().order_by('date_ajout')
        if not lignes:
            return []
        
        # Si tolérance n'est pas spécifiée, détecter automatiquement les pauses naturelles
        if tolerance_minutes == 5:
            tolerance_minutes = self._detecter_tolerance_automatique()
        
        sessions = []
        session_courante = []
        derniere_date = None
        
        for ligne in lignes:
            if not session_courante:
                # Première ligne : commencer une nouvelle session
                session_courante = [ligne]
                derniere_date = ligne.date_ajout
            else:
                # Calculer l'écart avec le dernier article ajouté
                ecart_minutes = (ligne.date_ajout - derniere_date).total_seconds() / 60
                
                if ecart_minutes <= tolerance_minutes:
                    # Écart acceptable : ajouter à la session courante
                    session_courante.append(ligne)
                    derniere_date = ligne.date_ajout
                else:
                    # Écart trop important : fermer la session courante et en créer une nouvelle
                    sessions.append({
                        'date_session': session_courante[0].date_ajout,
                        'lignes': session_courante.copy(),
                        'montant_total': sum(l.montant for l in session_courante),
                        'nombre_articles': sum(l.quantite for l in session_courante)
                    })
                    
                    # Commencer une nouvelle session
                    session_courante = [ligne]
                    derniere_date = ligne.date_ajout
        
        # Ajouter la dernière session
        if session_courante:
            sessions.append({
                'date_session': session_courante[0].date_ajout,
                'lignes': session_courante.copy(),
                'montant_total': sum(l.montant for l in session_courante),
                'nombre_articles': sum(l.quantite for l in session_courante)
            })
        
        return sessions
    
    def _detecter_tolerance_automatique(self):
        """
        Détecte automatiquement une tolérance appropriée basée sur les écarts entre les ajouts
        """
        lignes = self.lignes.all().order_by('date_ajout')
        if len(lignes) <= 1:
            return 30  # Valeur par défaut
        
        ecarts = []
        for i in range(1, len(lignes)):
            ecart = (lignes[i].date_ajout - lignes[i-1].date_ajout).total_seconds() / 60
            ecarts.append(ecart)
        
        # Trier les écarts pour identifier les "sauts" significatifs
        ecarts_tries = sorted(ecarts)
        
        # Si il y a des écarts > 60 minutes, utiliser 20 minutes comme seuil
        if any(e > 60 for e in ecarts_tries):
            return 20
        # Si il y a des écarts > 15 minutes, utiliser 10 minutes
        elif any(e > 15 for e in ecarts_tries):
            return 10
        # Sinon, utiliser 5 minutes
        else:
            return 5
    
    def ajouter_articles(self, articles_data, description_session=None):
        """
        Ajouter des articles à la vente avec traçabilité temporelle
        articles_data: liste de dict {'cahier': cahier_obj, 'quantite': int}
        description_session: description optionnelle de cette session d'ajout
        """
        lignes_creees = []
        maintenant = timezone.now()
        
        for article in articles_data:
            cahier = article['cahier']
            quantite = article['quantite']
            montant = Decimal(str(cahier.prix)) * Decimal(str(quantite))
            
            ligne = LigneVente.objects.create(
                vente=self,
                cahier=cahier,
                quantite=quantite,
                montant=montant
            )
            
            # La date_ajout sera automatiquement définie par auto_now_add
            lignes_creees.append(ligne)
            
            # Mettre à jour le stock si nécessaire
            if cahier.quantite_stock is not None:
                cahier.quantite_stock = max(0, cahier.quantite_stock - quantite)
                cahier.save()
        
        # Mettre à jour les informations de modification de la vente
        self.modified_at = maintenant
        self.derniere_modification_type = 'ajout_articles'
        if description_session:
            self.articles_ajoutes_session = description_session
        self.save()
        
        return lignes_creees

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
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_ajout = models.DateTimeField(auto_now_add=True, help_text="Date et heure d'ajout de cette ligne à la vente")
    
    class Meta:
        ordering = ['date_ajout']

    def save(self, *args, **kwargs):
        # Si pas de date_ajout définie, utiliser maintenant
        if not self.date_ajout:
            self.date_ajout = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        date_str = self.date_ajout.strftime('%d/%m/%Y %H:%M') if self.date_ajout else 'Date inconnue'
        return f"{self.quantite} x {self.cahier.titre} pour {self.vente.ecole.nom} le {date_str}"

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