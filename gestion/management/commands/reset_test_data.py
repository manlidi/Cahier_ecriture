from django.core.management.base import BaseCommand
from django.db import transaction
from gestion.models import Vente, Paiement, Ecoles, AnneeScolaire, Cahiers, LigneVente
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Supprime toutes les ventes et paiements et ajoute des données de test'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ecoles',
            type=int,
            default=5,
            help='Nombre d\'écoles à créer (défaut: 5)'
        )
        parser.add_argument(
            '--ventes-par-ecole',
            type=int,
            default=8,
            help='Nombre de ventes par école (défaut: 8)'
        )
        parser.add_argument(
            '--cahiers',
            type=int,
            default=6,
            help='Nombre de cahiers à créer (défaut: 6)'
        )
        parser.add_argument(
            '--keep-existing',
            action='store_true',
            help='Garder les données existantes (ne pas supprimer)'
        )

    def handle(self, *args, **options):
        nb_ecoles = options['ecoles']
        nb_ventes_par_ecole = options['ventes_par_ecole'] 
        nb_cahiers = options['cahiers']
        keep_existing = options['keep_existing']
        
        # Noms d'écoles variés
        noms_ecoles = [
            'ORIA', 'Saint Michel', 'Sainte Marie', 'École Primaire Centrale',
            'Complexe Scolaire du Plateau', 'Institut Sainte Thérèse', 
            'École Bilingue International', 'Groupe Scolaire les Palmiers',
            'École Saint Joseph', 'Complexe Scolaire moderne', 'École de la Paix',
            'Institut Saint Paul', 'École Notre Dame', 'Complexe Scolaire Elite',
            'École Française', 'Institut Polytechnique Junior'
        ]
        
        # Quartiers/adresses
        adresses = [
            'Quartier Résidentiel', 'Centre-ville', 'Plateau', 'Zone Industrielle',
            'Quartier des Ambassades', 'Cité Universitaire', 'Nouveau Quartier',
            'Zone Commerciale', 'Quartier Popular', 'Bord de Mer', 'Colline',
            'Quartier Administrative', 'Zone Périphérique', 'Centre Commercial'
        ]
        
        # Types de cahiers
        types_cahiers = [
            ('CI', 1100), ('CP', 1200), ('CE1', 1300), ('CE2', 1400), 
            ('CM1', 1500), ('CM2', 1600), ('6ème', 1700), ('5ème', 1800),
            ('4ème', 1900), ('3ème', 2000), ('2nde', 2100), ('1ère', 2200),
            ('Terminale', 2300), ('Maternelle', 900), ('Préscolaire', 800)
        ]

        with transaction.atomic():
            if not keep_existing:
                # Supprimer toutes les données existantes
                self.stdout.write('Suppression des données existantes...')
                Paiement.objects.all().delete()
                LigneVente.objects.all().delete()
                Vente.objects.all().delete()
                if not keep_existing:
                    Ecoles.objects.all().delete()
                    Cahiers.objects.all().delete()
            
            # Créer les cahiers
            self.stdout.write(f'Création de {nb_cahiers} cahiers...')
            cahiers = []
            for i in range(nb_cahiers):
                if i < len(types_cahiers):
                    titre, prix_base = types_cahiers[i]
                else:
                    titre = f'Cahier_{i+1}'
                    prix_base = 1000 + (i * 100)
                
                cahier, created = Cahiers.objects.get_or_create(
                    titre=titre,
                    defaults={
                        'prix': Decimal(str(prix_base + random.randint(-100, 200))),
                        'quantite_stock': random.randint(50, 200)
                    }
                )
                cahiers.append(cahier)
                if created:
                    self.stdout.write(f'  ✓ {cahier.titre} - {cahier.prix}F')
            
            # Créer les écoles
            self.stdout.write(f'Création de {nb_ecoles} écoles...')
            ecoles = []
            for i in range(nb_ecoles):
                nom = noms_ecoles[i % len(noms_ecoles)]
                if i >= len(noms_ecoles):
                    nom = f'{nom} {i // len(noms_ecoles) + 1}'
                    
                adresse = random.choice(adresses)
                
                ecole, created = Ecoles.objects.get_or_create(
                    nom=nom,
                    defaults={'adresse': adresse}
                )
                ecoles.append(ecole)
                if created:
                    self.stdout.write(f'  ✓ {ecole.nom} ({ecole.adresse})')
            
            # Récupérer/créer les années scolaires
            annee_2023_2024 = AnneeScolaire.objects.filter(annee_debut=2023, annee_fin=2024).first()
            annee_2024_2025 = AnneeScolaire.objects.filter(annee_debut=2024, annee_fin=2025).first()
            annee_2025_2026 = AnneeScolaire.objects.filter(annee_debut=2025, annee_fin=2026).first()
            
            if not annee_2023_2024:
                annee_2023_2024 = AnneeScolaire.creer_annee_scolaire(2023)
            if not annee_2024_2025:
                annee_2024_2025 = AnneeScolaire.creer_annee_scolaire(2024)
            if not annee_2025_2026:
                annee_2025_2026 = AnneeScolaire.creer_annee_scolaire(2025)
                # Marquer 2025-2026 comme année active
                annee_2025_2026.est_active = True
                annee_2025_2026.save()
            
            annees = [annee_2023_2024, annee_2024_2025, annee_2025_2026]
            
            self.stdout.write(f'Création de {nb_ventes_par_ecole} ventes par école...')
            
            # Générer les ventes pour chaque école
            total_ventes = 0
            for ecole in ecoles:
                self.stdout.write(f'\n  École: {ecole.nom}')
                
                for i in range(nb_ventes_par_ecole):
                    # Répartir les ventes sur les 3 années (plus de ventes récentes)
                    if i < nb_ventes_par_ecole * 0.1:  # 10% en 2023-2024
                        annee = annee_2023_2024
                        jours_ago = random.randint(400, 600)
                    elif i < nb_ventes_par_ecole * 0.4:  # 30% en 2024-2025  
                        annee = annee_2024_2025
                        jours_ago = random.randint(100, 400)
                    else:  # 60% en 2025-2026 (année courante)
                        annee = annee_2025_2026
                        jours_ago = random.randint(1, 100)
                    
                    # Créer la vente
                    vente = Vente.objects.create(
                        ecole=ecole,
                        annee_scolaire=annee,
                        created_at=timezone.now() - timedelta(days=jours_ago),
                        dette_precedente=Decimal('0') if random.random() > 0.2 else Decimal(str(random.randint(200, 1000)))
                    )
                    
                    # Ajouter 1 à 4 lignes de vente avec différentes sessions d'ajout
                    nb_lignes = random.randint(2, 4)  # Au moins 2 pour pouvoir avoir plusieurs sessions
                    montant_total_lignes = Decimal('0')
                    
                    # Simuler différentes sessions d'ajout (50% ont plusieurs sessions)
                    if nb_lignes > 1 and random.random() < 0.5:
                        # Plusieurs sessions : répartir les lignes en 2-3 sessions
                        nb_sessions = random.randint(2, min(3, nb_lignes))
                        lignes_data = []
                        
                        # Préparer toutes les lignes d'abord
                        for _ in range(nb_lignes):
                            lignes_data.append({
                                'cahier': random.choice(cahiers),
                                'quantite': random.randint(1, 3)
                            })
                        
                        # Répartir les lignes en sessions
                        lignes_par_session = []
                        lignes_restantes = lignes_data.copy()
                        
                        for session_idx in range(nb_sessions):
                            if session_idx == nb_sessions - 1:
                                # Dernière session : toutes les lignes restantes
                                session_lignes = lignes_restantes
                            else:
                                # Prendre 1-2 lignes pour cette session
                                nb_lignes_session = min(random.randint(1, 2), len(lignes_restantes))
                                session_lignes = lignes_restantes[:nb_lignes_session]
                                lignes_restantes = lignes_restantes[nb_lignes_session:]
                            
                            if session_lignes:
                                lignes_par_session.append(session_lignes)
                        
                        # Créer les lignes avec des dates d'ajout différentes
                        for session_idx, session_lignes in enumerate(lignes_par_session):
                            # Date d'ajout de la session (espacées de quelques heures/jours)
                            if session_idx == 0:
                                date_ajout_session = vente.created_at
                            else:
                                # Sessions suivantes : entre 2 heures et 3 jours plus tard
                                ecart_heures = random.randint(2, 72)  # 2h à 3 jours
                                date_ajout_session = vente.created_at + timedelta(hours=ecart_heures)
                            
                            for ligne_data in session_lignes:
                                cahier = ligne_data['cahier']
                                quantite = ligne_data['quantite']
                                montant = cahier.prix * quantite
                                
                                # Petite variation dans la session (quelques minutes)
                                variation_minutes = random.randint(0, 10)
                                date_ajout_finale = date_ajout_session + timedelta(minutes=variation_minutes)
                                
                                ligne = LigneVente.objects.create(
                                    vente=vente,
                                    cahier=cahier,
                                    quantite=quantite,
                                    montant=montant
                                )
                                # Modifier manuellement la date d'ajout
                                ligne.date_ajout = date_ajout_finale
                                ligne.save()
                                
                                montant_total_lignes += montant
                    else:
                        # Session unique : tous les articles ajoutés en même temps
                        for _ in range(nb_lignes):
                            cahier = random.choice(cahiers)
                            quantite = random.randint(1, 5)
                            montant = cahier.prix * quantite
                            
                            ligne = LigneVente.objects.create(
                                vente=vente,
                                cahier=cahier,
                                quantite=quantite,
                                montant=montant
                            )
                            # Petite variation (quelques minutes)
                            variation = random.randint(0, 5)
                            ligne.date_ajout = vente.created_at + timedelta(minutes=variation)
                            ligne.save()
                            
                            montant_total_lignes += montant
                    
                    # Générer des paiements (70% ont au moins un paiement)
                    if random.random() < 0.7:
                        montant_total_vente = montant_total_lignes + (vente.dette_precedente or Decimal('0'))
                        
                        # 30% payés complètement, 40% partiellement, 30% impayés
                        rand = random.random()
                        if rand < 0.3:  # Payé complètement
                            Paiement.objects.create(
                                vente=vente,
                                montant=montant_total_vente,
                                numero_tranche=1,
                                date_paiement=(vente.created_at + timedelta(days=random.randint(1, 30))).date()
                            )
                        elif rand < 0.7:  # Paiement partiel (1 à 3 tranches)
                            nb_tranches = random.randint(1, 3)
                            montant_restant = montant_total_vente
                            
                            for tranche in range(1, nb_tranches + 1):
                                if tranche == nb_tranches:
                                    # Dernière tranche partielle
                                    montant_tranche = montant_restant * Decimal(str(random.uniform(0.3, 0.8)))
                                else:
                                    # Tranche intermédiaire
                                    montant_tranche = montant_restant * Decimal(str(random.uniform(0.2, 0.5)))
                                
                                montant_tranche = montant_tranche.quantize(Decimal('0.01'))
                                
                                Paiement.objects.create(
                                    vente=vente,
                                    montant=montant_tranche,
                                    numero_tranche=tranche,
                                    date_paiement=(vente.created_at + timedelta(days=random.randint(1, 45))).date()
                                )
                                montant_restant -= montant_tranche
                        # Sinon, pas de paiement (impayé)
                    
                    total_ventes += 1
                    if i < 3:  # Afficher les 3 premières pour chaque école
                        statut = self._get_statut_vente(vente)
                        self.stdout.write(f'    ✓ Vente {annee} - {statut}')
                
                self.stdout.write(f'    → {nb_ventes_par_ecole} ventes créées')
            
            self.stdout.write(self.style.SUCCESS(f'\n🎉 {total_ventes} ventes créées avec succès !'))
            self._afficher_resume(ecoles)

    def _get_statut_vente(self, vente):
        """Calculer le statut d'une vente"""
        from django.db.models import Sum
        montant_lignes = vente.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        montant_total = montant_lignes + (vente.dette_precedente or Decimal('0'))
        montant_paye = vente.paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        montant_restant = montant_total - montant_paye
        
        if montant_restant <= 0:
            return 'Payé'
        elif montant_paye > 0:
            return 'Partiel'
        else:
            return 'Impayé'
    
    def _afficher_resume(self, ecoles):
        """Afficher un résumé des données créées"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 RÉSUMÉ DES DONNÉES CRÉÉES')
        self.stdout.write('='*60)
        
        total_ventes = 0
        total_montant = Decimal('0')
        total_paye = Decimal('0')
        
        for ecole in ecoles[:5]:  # Afficher les 5 premières écoles
            ventes = Vente.objects.filter(ecole=ecole)
            nb_ventes = ventes.count()
            total_ventes += nb_ventes
            
            self.stdout.write(f'\n🏫 {ecole.nom}:')
            
            for annee in AnneeScolaire.objects.all().order_by('annee_debut'):
                ventes_annee = ventes.filter(annee_scolaire=annee)
                if ventes_annee.exists():
                    stats = self._calculer_stats_annee(ventes_annee)
                    total_montant += stats['total']
                    total_paye += stats['paye']
                    
                    self.stdout.write(
                        f'  📅 {annee}: {stats["count"]} ventes | '
                        f'{stats["total"]}F total | {stats["paye"]}F payé | '
                        f'{stats["restant"]}F restant'
                    )
        
        if len(ecoles) > 5:
            self.stdout.write(f'\n... et {len(ecoles) - 5} autres écoles')
        
        self.stdout.write(f'\n📈 TOTAUX GÉNÉRAUX:')
        self.stdout.write(f'   🏫 Écoles: {len(ecoles)}')
        self.stdout.write(f'   📄 Ventes: {total_ventes}')
        self.stdout.write(f'   💰 Montant total: {total_montant}F')
        self.stdout.write(f'   💳 Montant payé: {total_paye}F')
        self.stdout.write(f'   ⚠️  Montant restant: {total_montant - total_paye}F')
        
    def _calculer_stats_annee(self, ventes_annee):
        """Calculer les statistiques pour une année"""
        from django.db.models import Sum
        
        count = ventes_annee.count()
        total = Decimal('0')
        paye = Decimal('0')
        
        for vente in ventes_annee:
            montant_lignes = vente.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
            montant_total_vente = montant_lignes + (vente.dette_precedente or Decimal('0'))
            montant_paye_vente = vente.paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
            
            total += montant_total_vente
            paye += montant_paye_vente
        
        return {
            'count': count,
            'total': total,
            'paye': paye, 
            'restant': total - paye
        }
