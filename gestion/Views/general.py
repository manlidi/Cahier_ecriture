from django.shortcuts import *
from gestion.models import Vente
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import cm
from io import BytesIO
from decimal import Decimal
import json
from django.utils import timezone
from datetime import datetime
import os
from django.conf import settings
from PyPDF2 import PdfReader, PdfWriter, PageObject
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle


def generer_facture_pdf(vente):
    styles_paragraph = getSampleStyleSheet()
    style_cellule = styles_paragraph['BodyText']
    style_cellule.wordWrap = 'CJK'
    style_cellule.leading = 11
    style_cellule.fontSize = 9

    # S'assurer que nous avons les dernières données
    vente.refresh_from_db()
    
    # Séparer les lignes originales et les ajouts récents
    lignes_originales = vente.get_lignes_originales()
    lignes_ajoutees = vente.get_lignes_ajoutees_recemment()
    
    if not lignes_originales and not lignes_ajoutees:
        raise ValueError("Impossible de générer une facture sans articles")

    # CORRECTION: Calculer avec des Decimal uniquement
    montant_total_articles = sum(Decimal(str(ligne.montant)) for ligne in vente.lignes.all())
    dette_precedente = Decimal(str(vente.dette_precedente)) if vente.dette_precedente else Decimal('0')
    montant_total = montant_total_articles + dette_precedente

    # Création du PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=6*cm, bottomMargin=4*cm)
    story = []
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_bold = styles["Heading4"]
    style_important = styles["Heading3"]

    story.append(Spacer(1, 0.5 * cm))

    # Style pour le nom de l'école
    style_ecole = ParagraphStyle(
        'EcoleStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        wordWrap='CJK',
        alignment=1,
        leading=10,
        spaceBefore=0,
        spaceAfter=0
    )

    est_modifiee = vente.modified_at is not None
    a_des_ajouts = len(lignes_ajoutees) > 0
    
    # Déterminer le type de modification
    type_modification = getattr(vente, 'derniere_modification_type', None)
    
    numero_facture = f"F-{datetime.now().year}-{str(vente.id)[:8]}"
    date_modif_str = vente.modified_at.strftime('%d-%m-%Y %H:%M') if vente.modified_at else "—"

    info_data = [
        ["ÉCOLE", "FACTURE", "DATE ÉDITION", "DATE MODIFICATION", "LIMITE PAIEMENT"],
        [Paragraph(vente.ecole.nom, style_ecole), 
        Paragraph(numero_facture), 
        datetime.now().strftime('%d-%m-%Y %H:%M'),
        date_modif_str,
        vente.date_paiement.strftime('%d-%m-%Y') if vente.date_paiement else "—"]
    ]

    info_table = Table(info_data, colWidths=[2.5*cm, 3.5*cm, 3*cm, 4*cm, 3*cm])
    info_table_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,1), 8),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
        ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ])
    
    if est_modifiee:
        info_table_style.add('BACKGROUND', (1,1), (1,1), colors.lightyellow)

    info_table.setStyle(info_table_style)   
    story.append(info_table)
    story.append(Spacer(0.1, 0.1 * cm))

    story.append(Paragraph("<b>ARTICLES COMMANDÉS</b>", style_bold))
    story.append(Spacer(0.1, 0.1*cm))
    
    lignes_facture_principal = [["Cahier", "Quantité", "Prix Unitaire", "Total"]]
    montant_original = Decimal('0')  # CORRECTION: Utiliser Decimal

    for ligne in lignes_originales:
        lignes_facture_principal.append([
            Paragraph(ligne.cahier.titre, style_cellule),
            str(ligne.quantite),
            f"{ligne.cahier.prix:.2f} F",
            f"{ligne.montant:.2f} F"
        ])
        montant_original += Decimal(str(ligne.montant))  # CORRECTION: Conversion en Decimal

    table_principal = Table(lignes_facture_principal, colWidths=[8*cm, 2.5*cm, 3*cm, 3*cm])
    table_style_principal = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.blue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 3),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('TOPPADDING', (0,1), (-1,-1), 3),
        ('BOTTOMPADDING', (0,1), (-1,-1), 3),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ])
    
    for i in range(1, len(lignes_facture_principal), 2):
        if i < len(lignes_facture_principal):
            table_style_principal.add('BACKGROUND', (0,i), (-1,i), colors.lightgrey)
        
    table_principal.setStyle(table_style_principal)
    story.append(table_principal)
    
    # Sous-total des articles originaux
    story.append(Spacer(0.1, 0.2*cm))
    story.append(Paragraph(f"<b>Sous-total articles commandés : {montant_original:.2f} F</b>", style_normal))

    # Section des articles ajoutés
    if a_des_ajouts and lignes_ajoutees:
        story.append(Spacer(0.2, 0.3*cm))
        story.append(Paragraph(f"<b>ARTICLES AJOUTÉS LE {date_modif_str}</b>", style_bold))
        story.append(Spacer(0.1, 0.1*cm))
        
        lignes_facture_ajouts = [["Cahier", "Quantité", "Prix Unitaire", "Total"]]
        montant_ajouts = Decimal('0')  # CORRECTION: Utiliser Decimal
        
        for ligne in lignes_ajoutees:
            lignes_facture_ajouts.append([
                Paragraph(ligne.cahier.titre, style_cellule),
                str(ligne.quantite),
                f"{ligne.cahier.prix:.2f} F",
                f"{ligne.montant:.2f} F"
            ])
            montant_ajouts += Decimal(str(ligne.montant))  # CORRECTION: Conversion en Decimal

        table_ajouts = Table(lignes_facture_ajouts, colWidths=[8*cm, 2.5*cm, 3*cm, 3*cm])
        table_style_ajouts = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.orange),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 3),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 3),
            ('BOTTOMPADDING', (0,1), (-1,-1), 3),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ])
        
        for i in range(1, len(lignes_facture_ajouts), 2):
            if i < len(lignes_facture_ajouts):
                table_style_ajouts.add('BACKGROUND', (0,i), (-1,i), colors.lightyellow)
            
        table_ajouts.setStyle(table_style_ajouts)
        story.append(table_ajouts)
        
        # Sous-total des ajouts
        story.append(Spacer(0.1, 0.2*cm))
        story.append(Paragraph(f"<b>Sous-total articles ajoutés : {montant_ajouts:.2f} F</b>", style_normal))

    story.append(Spacer(1, 0.3*cm))

    # Récapitulatif financier
    paiements_vente = vente.paiements.all().order_by('date_paiement')
    montant_paye = sum(Decimal(str(p.montant)) for p in paiements_vente)  # CORRECTION: Conversion en Decimal
    montant_restant = montant_total - montant_paye

    # Préparation des données du récapitulatif
    recap_data = []
    
    # Ligne articles
    recap_data.append([
        "Montant articles :",
        f"{montant_total_articles:.2f} F"
    ])
    
    # Ligne dette précédente (si elle existe)
    if dette_precedente > 0:  
        dette_description = vente.description_dette or "Dette année précédente"
        recap_data.append([
            f"{dette_description} :",
            f"{dette_precedente:.2f} F"  
        ])
    
    # Ligne total
    recap_data.append([
        "MONTANT TOTAL :",
        f"{montant_total:.2f} F"
    ])
    
    # Ligne montant payé
    recap_data.append([
        "Montant payé :",
        f"{montant_paye:.2f} F" if montant_paye > 0 else "Aucun paiement"
    ])
    
    # Ligne montant restant
    recap_data.append([
        "MONTANT RESTANT :",
        f"{montant_restant:.2f} F" if montant_restant > 0 else "ENTIÈREMENT RÉGLÉE"
    ])

    recap_table = Table(recap_data, colWidths=[10*cm, 6.5*cm])
    recap_table_style = TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),     
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),    
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ])
    
    # Mise en forme spéciale pour certaines lignes
    if dette_precedente > 0:  # CORRECTION: Utiliser dette_precedente
        # Ligne dette en orange
        recap_table_style.add('BACKGROUND', (0,1), (-1,1), colors.lightyellow)
        # Ligne total en gris
        recap_table_style.add('BACKGROUND', (0,2), (-1,2), colors.lightgrey)
        recap_table_style.add('FONTNAME', (0,2), (-1,2), 'Helvetica-Bold')
        # Ligne restant
        ligne_restant = 4
    else:
        # Ligne total en gris
        recap_table_style.add('BACKGROUND', (0,1), (-1,1), colors.lightgrey)
        recap_table_style.add('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')
        # Ligne restant
        ligne_restant = 3
    
    # Colorer la ligne "montant restant" selon l'état
    if montant_restant <= 0:
        recap_table_style.add('BACKGROUND', (0,ligne_restant), (-1,ligne_restant), colors.lightgreen)
        recap_table_style.add('TEXTCOLOR', (0,ligne_restant), (-1,ligne_restant), colors.darkgreen)
        recap_table_style.add('FONTNAME', (0,ligne_restant), (-1,ligne_restant), 'Helvetica-Bold')
    else:
        recap_table_style.add('BACKGROUND', (0,ligne_restant), (-1,ligne_restant), colors.lightcoral)
        recap_table_style.add('TEXTCOLOR', (0,ligne_restant), (-1,ligne_restant), colors.darkred)
        recap_table_style.add('FONTNAME', (0,ligne_restant), (-1,ligne_restant), 'Helvetica-Bold')
        
        # Vérifier si en retard
        try:
            if vente.date_paiement and vente.date_paiement.date() < timezone.now().date():
                story.append(Spacer(0.1, 0.1*cm))
                story.append(Paragraph(
                    f"<b><font color='red'>PAIEMENT EN RETARD</font></b>", 
                    style_important
                ))
        except AttributeError:
            # Si date_paiement est None
            pass
    
    recap_table.setStyle(recap_table_style)
    story.append(recap_table)

    # Construire le PDF
    doc.build(story)
    buffer.seek(0)

    # Fusion avec le papier en-tête
    papier_en_tete_path = os.path.join(settings.BASE_DIR, 'static/admin/papier1.pdf')
    final_buffer = BytesIO()

    if os.path.exists(papier_en_tete_path):
        try:
            modele_pdf = PdfReader(papier_en_tete_path)
            tableau_pdf = PdfReader(buffer)
            writer = PdfWriter()

            for page_tableau in tableau_pdf.pages:
                fond = modele_pdf.pages[0]
                page_fusionnee = PageObject.create_blank_page(
                    width=fond.mediabox.width,
                    height=fond.mediabox.height
                )
                page_fusionnee.merge_page(fond)
                page_fusionnee.merge_page(page_tableau)
                writer.add_page(page_fusionnee)

            writer.write(final_buffer)
            final_buffer.seek(0)

        except Exception as pdf_error:
            print(f"Erreur lors de la fusion PDF : {pdf_error}")
            final_buffer = buffer
    else:
        print(f"Fichier papier en-tête introuvable : {papier_en_tete_path}")
        final_buffer = buffer

    return final_buffer

def calculer_dette_ecole(ecole, vente_exclue=None):
    """Calcule la dette totale d'une école en excluant optionnellement une vente"""
    ventes_query = Vente.objects.filter(ecole=ecole)
    
    if vente_exclue:
        ventes_query = ventes_query.exclude(id=vente_exclue.id)
    
    dette_totale = Decimal('0')
    for vente in ventes_query:
        montant_restant = vente.montant_restant()
        if montant_restant > 0:
            dette_totale += montant_restant
    
    return dette_totale

