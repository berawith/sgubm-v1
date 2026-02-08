import io
import pandas as pd
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

class ReportService:
    """ Servio para generación de reportes premium (PDF, Excel) """

    @staticmethod
    def generate_payments_pdf(payments, start_date=None, end_date=None):
        """ Genera un PDF profesional con el listado de pagos """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), 
                               rightMargin=30, leftMargin=30, 
                               topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        # Estilo de Titulo
        title_style = ParagraphStyle(
            'PremiumTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1e293b'),
            alignment=1,
            spaceAfter=20
        )

        # Header Info
        header_text = "REPORTE DE RECAUDACIÓN"
        if start_date and end_date:
            header_text += f" ({start_date} al {end_date})"
        
        elements.append(Paragraph(header_text, title_style))
        elements.append(Spacer(1, 12))

        # Tabla de Datos
        data = [['ID', 'CLIENTE', 'CÓDIGO', 'FECHA/HORA', 'MONTO', 'MÉTODO', 'REFERENCIA']]
        total_amount = 0

        for p in payments:
            client_name = p.client.legal_name if p.client else 'N/A'
            subs_code = p.client.subscriber_code if p.client else '---'
            payment_time = p.payment_date.strftime('%d/%m/%Y %H:%M')
            amount_str = f"${p.amount:,.2f}"
            total_amount += p.amount

            data.append([
                p.id,
                Paragraph(client_name[:30] + ('...' if len(client_name)>30 else ''), styles['Normal']),
                subs_code,
                payment_time,
                amount_str,
                p.payment_method.capitalize() if p.payment_method else '---',
                p.reference or '---'
            ])

        # Fila de Total
        data.append(['', '', '', 'TOTAL GENERAL:', f"${total_amount:,.2f}", '', ''])

        table = Table(data, repeatRows=1, colWidths=[0.5*inch, 2.5*inch, 1*inch, 1.5*inch, 1*inch, 1*inch, 2*inch])
        
        # Estilo de la Tabla
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6366f1')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (1,1), (-1,-2), [colors.whitesmoke, colors.white])
        ])
        table.setStyle(style)
        elements.append(table)

        # Footer
        elements.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
        elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} - SGUBM Premium Billing", footer_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_payments_excel(payments):
        """ Genera un Excel formateado con el listado de pagos """
        data = []
        for p in payments:
            data.append({
                'ID': p.id,
                'Cliente': p.client.legal_name if p.client else 'N/A',
                'Código': p.client.subscriber_code if p.client else '---',
                'Fecha': p.payment_date.replace(tzinfo=None), # Pandas prefiere sin timezone para Excel compatible
                'Monto (COP)': p.amount,
                'Moneda': p.currency,
                'Método': p.payment_method,
                'Referencia': p.reference,
                'Notas': p.notes
            })
        
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        
        try:
            # Intentar usar XlsxWriter para formato "bonito"
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Pagos')
                
                workbook = writer.book
                worksheet = writer.sheets['Pagos']
                
                # Formatos
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#6366f1',
                    'font_color': 'white',
                    'border': 1
                })
                
                money_format = workbook.add_format({'num_format': '$#,##0.00'})
                date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm'})

                # Aplicar formatos
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    
                worksheet.set_column('B:B', 30) # Cliente
                worksheet.set_column('D:D', 20, date_format) # Fecha
                worksheet.set_column('E:E', 15, money_format) # Monto
                worksheet.set_column('G:I', 20) # Referencias
        except Exception as e:
            # Fallback a motor por defecto (openpyxl o básico) si xlsxwriter falla
            print(f"Error using xlsxwriter, falling back: {e}")
            df.to_excel(buffer, index=False, sheet_name='Pagos')

        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_debtors_pdf(debtors):
        """ Genera reporte PDF de morosos premium """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                               rightMargin=40, leftMargin=40, 
                               topMargin=40, bottomMargin=40)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'PremiumTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#991b1b'), # Rojo oscuro para morosos
            alignment=1,
            spaceAfter=20
        )
        elements.append(Paragraph("LISTADO DE CLIENTES CON DEUDA (MOROSOS)", title_style))
        elements.append(Spacer(1, 12))

        data = [['CÓDIGO', 'CLIENTE', 'TELÉFONO', 'DEUDA TOT.']]
        total_debt = 0

        for c in debtors:
            debt = (c.account_balance or 0)
            total_debt += debt
            data.append([
                c.subscriber_code or '---',
                Paragraph(c.legal_name[:45] if c.legal_name else 'N/A', styles['Normal']),
                c.phone or '---',
                f"${debt:,.2f}"
            ])

        data.append(['', 'TOTAL CARTERA PENDIENTE:', '', f"${total_debt:,.2f}"])

        table = Table(data, repeatRows=1, colWidths=[1*inch, 4*inch, 1.2*inch, 1.3*inch])
        
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('ALIGN', (-1,1), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#fee2e2')), # Rojo muy claro para total
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (1,1), (-1,-2), [colors.whitesmoke, colors.white])
        ])
        table.setStyle(style)
        elements.append(table)
        
        elements.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
        elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} - Cartera Pendiente SGUBM", footer_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_debtors_excel(debtors):
        """ Genera reporte Excel de morosos premium """
        data = []
        for c in debtors:
            data.append({
                'Ref': c.id,
                'Código': c.subscriber_code or '---',
                'Cliente': c.legal_name or 'N/A',
                'Teléfono': c.phone or '---',
                'Deuda Total (COP)': c.account_balance or 0,
                'Dirección': c.address or '---'
            })
        
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        
        try:
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Morosos')
                
                workbook = writer.book
                worksheet = writer.sheets['Morosos']
                
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#ef4444',
                    'font_color': 'white',
                    'border': 1
                })
                
                money_format = workbook.add_format({'num_format': '$#,##0.00'})

                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    
                worksheet.set_column('C:C', 35) # Cliente
                worksheet.set_column('E:E', 18, money_format) # Deuda
                worksheet.set_column('F:F', 40) # Dirección
        except Exception as e:
            df.to_excel(buffer, index=False, sheet_name='Morosos')

        buffer.seek(0)
        return buffer
