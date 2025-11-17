from django.shortcuts import *
from gestion.models import Ecoles

def allecoles(request):
    ecoles = Ecoles.objects.all()
    return render(request, 'ecoles.html', {'ecoles': ecoles})


def ajouter_ecole(request):
    if request.method == "POST":
        nom = request.POST.get("nom")
        adresse = request.POST.get("adresse")
        representant = request.POST.get("representant")
        Ecoles.objects.create(nom=nom, adresse=adresse, representant=representant)
    return redirect('ecoles')


def modifier_ecole(request, ecole_id):
    ecole = get_object_or_404(Ecoles, id=ecole_id)
    if request.method == "POST":
        ecole.nom = request.POST.get("nom")
        ecole.adresse = request.POST.get("adresse")
        ecole.representant = request.POST.get("representant")
        ecole.save()
    return redirect('ecoles')


def supprimer_ecole(request, ecole_id):
    ecole = get_object_or_404(Ecoles, id=ecole_id)
    ecole.delete()
    return redirect('ecoles')
