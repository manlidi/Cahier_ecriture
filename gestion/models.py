from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
    

class Cahiers(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.TextField()
    prix = models.IntegerField()
    quantite_stock = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Ecoles(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.TextField()
    adresse = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Vente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ecole = models.ForeignKey(Ecoles, on_delete=models.CASCADE, related_name='ventes')
    date_paiement = models.DateTimeField(null=True)  
    facture_pdf = models.FileField(upload_to='factures/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def montant_total(self):
        return sum(ligne.montant for ligne in self.lignes.all())

    def __str__(self):
        return f"Vente à {self.ecole.nom} le {self.date_paiement.strftime('%d/%m/%Y') if self.date_paiement else 'Date inconnue'}"
    
    def montant_restant(self):
        return self.montant_total - self.montant_paye
    
    @property
    def montant_paye(self):
        return sum(p.montant for p in self.paiements.all())

    def est_reglee(self):
        return self.montant_restant() <= 0
    
    def nombre_tranches_payees(self):
        return self.paiements.count()
    
    def peut_ajouter_tranche(self):
        return self.nombre_tranches_payees() < 3 and not self.est_reglee()
    
    def est_en_retard(self): 
        """Vérifie si la date limite de paiement est dépassée"""
        if self.date_paiement and not self.est_reglee():
            return timezone.now() > self.date_paiement
        return False
    
    def statut_paiement(self):
        if self.est_reglee():
            return "Réglée"
        elif self.est_en_retard():
            return "En retard"
        else:
            return "En cours"


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
    montant = models.IntegerField()

    def save(self, *args, **kwargs):
        self.montant = self.quantite * self.cahier.prix
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantite} x {self.cahier.titre} pour {self.vente.ecole.nom}"