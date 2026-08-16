import io
import os
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def _get_logo_image(height=45):
    """Devuelve un objeto Image de ReportLab con el logo si existe el archivo."""
    logo_path = settings.BASE_DIR / 'static' / 'logo yimmi.png'
    if os.path.exists(logo_path):
        try:
            return Image(str(logo_path), height=height, width=height * 1.5)
        except Exception:
            return None
    return None

def generar_pdf_venta(venta):
    """Genera un comprobante de venta en formato PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0d6efd'),
        alignment=0
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#6c757d')
    )
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold'
    )

    # Encabezado con Logo
    logo_img = _get_logo_image(height=40)
    header_text = [
        Paragraph("SISTEMA INVEN - COMPROBANTE DE VENTA", title_style),
        Paragraph(f"Comprobante de Venta #{venta.id} | Fecha: {venta.created_at.strftime('%Y-%m-%d %H:%M')}", subtitle_style)
    ]
    if logo_img:
        header_table = Table([[logo_img, header_text]], colWidths=[80, 460])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(header_table)
    else:
        story.extend(header_text)

    story.append(Spacer(1, 15))


    # Información del cliente y la venta
    cliente_nombre = venta.cliente.nombre if venta.cliente else "Cliente General"
    cliente_doc = str(venta.cliente.numero_documento) if venta.cliente else "N/A"
    ruta_nombre = venta.ruta.nombre if venta.ruta else "N/A"
    vendedor_nombre = venta.usuario.nombre if venta.usuario else "N/A"

    info_data = [
        [Paragraph("<b>Cliente:</b>", styles['Normal']), Paragraph(f"{cliente_nombre} ({cliente_doc})", styles['Normal']),
         Paragraph("<b>Tipo Venta:</b>", styles['Normal']), Paragraph(f"{venta.tipo}", styles['Normal'])],
        [Paragraph("<b>Ruta:</b>", styles['Normal']), Paragraph(ruta_nombre, styles['Normal']),
         Paragraph("<b>Estado:</b>", styles['Normal']), Paragraph(f"{venta.estado}", styles['Normal'])],
        [Paragraph("<b>Vendedor:</b>", styles['Normal']), Paragraph(vendedor_nombre, styles['Normal']),
         Paragraph("<b>Frecuencia:</b>", styles['Normal']), Paragraph(f"{venta.frecuencia_cobro}", styles['Normal'])],
    ]
    info_table = Table(info_data, colWidths=[80, 180, 90, 180])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    # Detalle de productos
    story.append(Paragraph("Detalle de Productos", bold_style))
    story.append(Spacer(1, 5))

    detalles_data = [["Producto", "Cantidad", "Precio Unit.", "Subtotal"]]
    for det in venta.detalleventa_set.all():
        detalles_data.append([
            det.producto.nombre if det.producto else "N/A",
            str(det.cantidad),
            f"${det.precio:.2f}",
            f"${det.subtotal:.2f}"
        ])

    det_table = Table(detalles_data, colWidths=[240, 80, 100, 110])
    det_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 15))

    # Resumen de Totales
    totales_data = [
        ["Subtotal:", f"${venta.subtotal:.2f}"],
        ["Descuento:", f"${venta.descuento:.2f}"],
        ["Total Venta:", f"${venta.total:.2f}"],
        ["Saldo Pendiente:", f"${venta.saldo:.2f}"]
    ]
    tot_table = Table(totales_data, colWidths=[420, 110])
    tot_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,2), (-1,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(tot_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def generar_pdf_cobro(cobro):
    """Genera un recibo de cobro en formato PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CobroTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#198754')
    )
    subtitle_style = ParagraphStyle(
        'CobroSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#6c757d')
    )

    # Encabezado con Logo
    logo_img = _get_logo_image(height=40)
    header_text = [
        Paragraph("SISTEMA INVEN - RECIBO DE COBRO", title_style),
        Paragraph(f"Recibo #{cobro.id} | Fecha de Pago: {cobro.created_at.strftime('%Y-%m-%d %H:%M')}", subtitle_style)
    ]
    if logo_img:
        header_table = Table([[logo_img, header_text]], colWidths=[80, 460])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(header_table)
    else:
        story.extend(header_text)

    story.append(Spacer(1, 15))


    venta = cobro.venta
    cliente_nombre = venta.cliente.nombre if venta.cliente else "Cliente General"
    cliente_doc = str(venta.cliente.numero_documento) if venta.cliente else "N/A"

    data = [
        [Paragraph("<b>Cliente:</b>", styles['Normal']), Paragraph(f"{cliente_nombre} ({cliente_doc})", styles['Normal'])],
        [Paragraph("<b>Venta Asociada:</b>", styles['Normal']), Paragraph(f"Venta #{venta.id}", styles['Normal'])],
        [Paragraph("<b>Monto Abonado:</b>", styles['Normal']), Paragraph(f"<b>${cobro.monto:.2f}</b>", styles['Normal'])],
        [Paragraph("<b>Método de Pago:</b>", styles['Normal']), Paragraph(f"{cobro.metodo}", styles['Normal'])],
        [Paragraph("<b>Saldo Restante Venta:</b>", styles['Normal']), Paragraph(f"${venta.saldo:.2f}", styles['Normal'])],
        [Paragraph("<b>Observaciones:</b>", styles['Normal']), Paragraph(cobro.observacion or "Sin observaciones", styles['Normal'])],
    ]
    table = Table(data, colWidths=[150, 380])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer
