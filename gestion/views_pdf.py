from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils import timezone
from django.conf import settings
from gestion.models import Vente
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
from PyPDF2 import PdfReader, PdfWriter, PageObject
from io import BytesIO
import os
from decimal import Decimal


def generer_facture_pdf(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)
    
    # S'assurer que nous avons les dernières données
    vente.refresh_from_db()
    
    # Créer le buffer pour le PDF
    buffer = BytesIO()
    
    # Styles
    styles_paragraph = getSampleStyleSheet()
    style_cellule = styles_paragraph['BodyText']
    style_cellule.wordWrap = 'CJK'
    style_cellule.leading = 11
    style_cellule.fontSize = 9
    
    # Créer le document PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=5.5*cm, bottomMargin=4*cm)
    
    story = []
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_bold = styles["Heading4"]
    style_important = styles["Heading3"]

    
    # Style pour le nom de l'école
    style_header = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        alignment=1,  
        leading=10,
        spaceBefore=0,
        spaceAfter=0,
        wordWrap='LTR'   
    )

    # Style pour les valeurs
    style_ecole = ParagraphStyle(
        'EcoleStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        alignment=1,  
        leading=10,
        spaceBefore=0,
        spaceAfter=0,
        wordWrap='LTR'   
    )
    
    # Informations de la facture
    numero_facture = f"F-{datetime.now().year}-{str(vente.id)[:8]}"
    date_modif_str = vente.modified_at.strftime('%d-%m-%Y') if vente.modified_at else "—"
    date_paiement = vente.date_paiement.strftime('%d-%m-%Y') if vente.date_paiement else "—"
    
    # Tableau d'en-tête avec informations
    info_data = [
        [
            Paragraph("ÉCOLE", style_header),
            Paragraph("FACTURE", style_header),
            Paragraph("DATE D'ÉDITION", style_header),
            Paragraph("DATE DE MODIFICATION", style_header),
            Paragraph("DATE DE PAIEMENT", style_header),
            Paragraph("ANNÉE SCOLAIRE", style_header)
        ],
        [
            Paragraph(vente.ecole.nom, style_ecole),
            Paragraph(numero_facture, style_ecole),
            Paragraph(datetime.now().strftime('%d-%m-%Y'), style_ecole),
            Paragraph(date_modif_str, style_ecole),
            Paragraph(date_paiement, style_ecole),
            Paragraph(str(vente.annee_scolaire), style_ecole)
        ]
    ]

    # Largeurs de colonnes
    info_table = Table(info_data, colWidths=[4*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])

    # Style du tableau
    info_table_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ])

    info_table.setStyle(info_table_style)

    story.append(info_table)
    story.append(Spacer(0.1, 0.1 * cm))
    
    # Récupérer toutes les dettes de l'école par année
    dettes_par_annee = vente.get_dettes_par_annee_ecole()
    total_dettes_ecole = vente.get_total_dettes_ecole()
    
    # Affichage des dettes par année (s'il y en a)
    if len(dettes_par_annee) > 0:
        # Exclure la vente courante du calcul des autres dettes à afficher
        dettes_autres = {k: v for k, v in dettes_par_annee.items() 
                        if any(vte.id != vente.id for vte in v['ventes'])}
        
        if dettes_autres:
            story.append(Paragraph("<b>HISTORIQUE DES DETTES PAR ANNÉE SCOLAIRE</b>", style_bold))
            story.append(Spacer(0.1, 0.1*cm))
            
            # Tableau des dettes par année
            dettes_data = [["Année scolaire", "Montant articles", "Total", "Payé", "Restant dû"]]
            
            for annee_str, dette_info in dettes_autres.items():
                dettes_data.append([
                    str(dette_info['annee_scolaire']),
                    f"{dette_info['montant_articles']:.2f} F",
                    f"{dette_info['montant_total']:.2f} F",
                    f"{dette_info['montant_paye']:.2f} F",
                    f"{dette_info['montant_restant']:.2f} F"
                ])
            
            table_dettes = Table(dettes_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm, 3*cm])
            table_style_dettes = TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.darkred),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 8),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 3),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 8),
                ('TOPPADDING', (0,1), (-1,-1), 3),
                ('BOTTOMPADDING', (0,1), (-1,-1), 3),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ])
            
            # Alterner les couleurs des lignes
            for i in range(1, len(dettes_data), 2):
                if i < len(dettes_data):
                    table_style_dettes.add('BACKGROUND', (0,i), (-1,i), colors.lightgrey)
            
            table_dettes.setStyle(table_style_dettes)
            story.append(table_dettes)
            story.append(Spacer(0.2, 0.3*cm))
    
    # Sessions d'articles de cette facture
    sessions = vente.get_articles_par_session()
    
    if sessions:
        story.append(Paragraph("<b>ARTICLES DE CETTE FACTURE PAR SESSION</b>", style_bold))
        story.append(Spacer(0.1, 0.1*cm))
        
        for i, session in enumerate(sessions, 1):
            # Titre de la session
            session_title = f"SESSION #{i} - {session['date_session'].strftime('%d-%m-%Y %H:%M')}"
            story.append(Paragraph(f"<b>{session_title}</b>", style_normal))
            story.append(Spacer(0.1, 0.1*cm))
            
            # Tableau des articles de cette session
            session_data = [["Cahier", "Quantité", "Prix Unitaire", "Total"]]
            
            for ligne in session['lignes']:
                session_data.append([
                    Paragraph(ligne.cahier.titre, style_cellule),
                    str(ligne.quantite),
                    f"{ligne.cahier.prix:.2f} F",
                    f"{ligne.montant:.2f} F"
                ])
            
            table_session = Table(session_data, colWidths=[8*cm, 2.5*cm, 3*cm, 3*cm])
            table_style_session = TableStyle([
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
            
            # Alterner les couleurs des lignes
            for j in range(1, len(session_data), 2):
                if j < len(session_data):
                    table_style_session.add('BACKGROUND', (0,j), (-1,j), colors.lightgrey)
            
            table_session.setStyle(table_style_session)
            story.append(table_session)
            
            # Sous-total de la session
            story.append(Spacer(0.1, 0.2*cm))
            story.append(Paragraph(f"<b>Sous-total session #{i} : {session['montant_total']:.2f} F</b>", style_normal))
            story.append(Spacer(0.2, 0.3*cm))
    
    # Récapitulatif financier
    montant_total_articles = sum(Decimal(str(ligne.montant)) for ligne in vente.lignes.all())
    montant_total_facture = montant_total_articles
    
    # Calculs des paiements
    paiements_vente = vente.paiements.all().order_by('date_paiement')
    montant_paye = sum(Decimal(str(p.montant)) for p in paiements_vente)
    montant_restant_facture = montant_total_facture - montant_paye
    
    story.append(Spacer(1, 0.3*cm))
    
    # Préparation des données du récapitulatif
    recap_data = []
    
    # Ligne articles
    recap_data.append([
        "Sous-total des articles :",
        f"{montant_total_articles:.2f} F"
    ])
    
    # Ligne total de cette facture
    recap_data.append([
        "Total de la facture :",
        f"{montant_total_facture:.2f} F"
    ])
    
    # Ligne montant payé
    recap_data.append([
        "Paiements reçus :",
        f"{montant_paye:.2f} F" if montant_paye > 0 else "Aucun paiement"
    ])
    
    # Ligne montant restant sur cette facture
    recap_data.append([
        "Solde restant dû :",
        f"{montant_restant_facture:.2f} F" if montant_restant_facture > 0 else "ENTIÈREMENT RÉGLÉE"
    ])
    
    # Si il y a d'autres dettes, ajouter le total global
    if len(dettes_par_annee) > 1:
        recap_data.append([
            "Encours global de l’établissement :",
            f"{total_dettes_ecole:.2f} F"
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
    ligne_total_facture = 1  
    ligne_restant_facture = 3  
    
    # Ligne total facture en gris
    recap_table_style.add('BACKGROUND', (0,ligne_total_facture), (-1,ligne_total_facture), colors.lightgrey)
    recap_table_style.add('FONTNAME', (0,ligne_total_facture), (-1,ligne_total_facture), 'Helvetica-Bold')
    
    # Colorer la ligne "montant restant facture" selon l'état
    if montant_restant_facture <= 0:
        recap_table_style.add('BACKGROUND', (0,ligne_restant_facture), (-1,ligne_restant_facture), colors.lightgreen)
        recap_table_style.add('TEXTCOLOR', (0,ligne_restant_facture), (-1,ligne_restant_facture), colors.darkgreen)
        recap_table_style.add('FONTNAME', (0,ligne_restant_facture), (-1,ligne_restant_facture), 'Helvetica-Bold')
    else:
        recap_table_style.add('BACKGROUND', (0,ligne_restant_facture), (-1,ligne_restant_facture), colors.lightcoral)
        recap_table_style.add('TEXTCOLOR', (0,ligne_restant_facture), (-1,ligne_restant_facture), colors.darkred)
        recap_table_style.add('FONTNAME', (0,ligne_restant_facture), (-1,ligne_restant_facture), 'Helvetica-Bold')
    
    # Si il y a un total des dettes école, le mettre en évidence
    if len(dettes_par_annee) > 1:
        ligne_total_ecole = len(recap_data) - 1
        recap_table_style.add('BACKGROUND', (0,ligne_total_ecole), (-1,ligne_total_ecole), colors.lightyellow)
        recap_table_style.add('FONTNAME', (0,ligne_total_ecole), (-1,ligne_total_ecole), 'Helvetica-Bold')
        recap_table_style.add('FONTSIZE', (0,ligne_total_ecole), (-1,ligne_total_ecole), 11)
    
    recap_table.setStyle(recap_table_style)
    story.append(recap_table)
    
    # Construire le PDF principal
    doc.build(story)
    buffer.seek(0)
    
    # Tentative de fusion avec le papier en-tête
    papier_en_tete_path = os.path.join(settings.BASE_DIR, 'static/admin/fa.pdf')
    papier_signature_path = os.path.join(settings.BASE_DIR, 'static/admin/FACTURE.pdf')
    final_buffer = BytesIO()

    if os.path.exists(papier_en_tete_path) and os.path.exists(papier_signature_path):
        try:
            modele_pdf = PdfReader(papier_en_tete_path)  
            modele_signature_pdf = PdfReader(papier_signature_path) 
            tableau_pdf = PdfReader(buffer)
            writer = PdfWriter()
            
            total_pages = len(tableau_pdf.pages)
            
            for idx, page_tableau in enumerate(tableau_pdf.pages):
                if idx == total_pages - 1: 
                    fond = modele_signature_pdf.pages[0]
                else:
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
        print(f"Fichier papier en-tête introuvable")
        final_buffer = buffer

    
    # Créer la réponse HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="facture_{vente.ecole.nom.replace(" ", "_")}_{vente.id}.pdf"'
    response.write(final_buffer.getvalue())
    
    return response
