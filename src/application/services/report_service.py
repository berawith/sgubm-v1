import io
import pandas as pd
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend

class ReportService:
    """ Servio para generación de reportes premium (PDF, Excel) """

    @staticmethod
    def format_bandwidth(value):
        """Convierte valores de ancho de banda (bits) a formato legible (M, k)"""
        if not value or value == 'N/A':
            return 'N/A'
        
        def convert(v):
            try:
                num = int(v)
                if num >= 1000000:
                    return f"{num // 1000000}M"
                if num >= 1000:
                    return f"{num // 1000}k"
                return str(num)
            except (ValueError, TypeError):
                return str(v)

        # Manejar formato MikroTik "rate/rate" (upload/download)
        if isinstance(value, str) and '/' in value:
            return "/".join(convert(v.strip()) for v in value.split('/'))
        
        return convert(value)

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

    @staticmethod
    def generate_router_analysis_pdf(router_stats):
        """
        Genera un reporte analítico por Router con gráficas
        router_stats: Lista de dicts {name, total_clients, active, cut, retired, solvent, debtor, total_debt, potential_revenue}
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                               rightMargin=30, leftMargin=30, 
                               topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            'PremiumTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#4f46e5'),
            alignment=1,
            spaceAfter=20
        )
        elements.append(Paragraph("ANÁLISIS FINANCIERO POR ROUTER", title_style))
        elements.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        for router in router_stats:
            # Router Header
            r_header = ParagraphStyle('RouterHeader', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#1e293b'), spaceBefore=15)
            elements.append(Paragraph(f"📡 Router: {router['name']}", r_header))
            
            # Stats Summary Text
            stats_text = [
                f"<b>Total Clientes:</b> {router['total_clients']}",
                f"<b>Ingreso Potencial:</b> ${router['potential_revenue']:,.2f}",
                f"<b>Cartera Vencida (Deuda):</b> <font color='red'>${router['total_debt']:,.2f}</font>"
            ]
            elements.append(Paragraph(" | ".join(stats_text), styles['Normal']))
            elements.append(Spacer(1, 10))

            # Charts Container (Table for layout)
            # Pie 1: Status (Active/Cut/Retired)
            d1 = Drawing(200, 100)
            pc1 = Pie()
            pc1.x = 50
            pc1.y = 10
            pc1.width = 80
            pc1.height = 80
            pc1.data = [router['active'], router['cut'], router['retired']]
            pc1.labels = [f"Activos ({router['active']})", f"Cortados ({router['cut']})", f"Retirados ({router['retired']})"]
            pc1.slices.strokeWidth = 0.5
            pc1.slices[0].fillColor = colors.HexColor('#10b981') # Green
            pc1.slices[1].fillColor = colors.HexColor('#ef4444') # Red
            pc1.slices[2].fillColor = colors.HexColor('#64748b') # Grey
            d1.add(pc1)

            # Pie 2: Financial (Solvent/Debtor) - Excluding Retired
            active_cut_total = router['active'] + router['cut']
            d2 = Drawing(200, 100)
            
            # Solo mostrar gráfico financiero si hay datos relevantes
            has_financial_data = (router['solvent'] + router['debtor']) > 0
            
            if has_financial_data:
                pc2 = Pie()
                pc2.x = 50
                pc2.y = 10
                pc2.width = 80
                pc2.height = 80
                pc2.data = [router['solvent'], router['debtor']]
                pc2.labels = [f"Solventes ({router['solvent']})", f"Deudores ({router['debtor']})"]
                pc2.slices.strokeWidth = 0.5
                pc2.slices[0].fillColor = colors.HexColor('#3b82f6') # Blue
                pc2.slices[1].fillColor = colors.HexColor('#f59e0b') # Orange
                d2.add(pc2)
            
            # Layout Charts
            chart_table = Table([[d1, d2], ["Estado del Servicio", "Salud Financiera"]], colWidths=[3*inch, 3*inch])
            chart_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTSIZE', (0,1), (-1,1), 9),
                ('TEXTCOLOR', (0,1), (-1,1), colors.grey)
            ]))
            elements.append(chart_table)
            elements.append(Spacer(1, 10))

            # Financial Collections Summary (Red Box equivalent)
            # Create a table for financial highlight
            col_data = [
                # Headers
                [f"META FACTURACIÓN", f"RECAUDADO (En Periodo)", f"CARTERA VENCIDA"],
                # Values
                [f"${router['potential_revenue']:,.2f}", f"${router.get('collected', 0):,.2f}", f"${router['total_debt']:,.2f}"]
            ]
            
            col_table = Table(col_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
            col_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 8),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#64748b')), # Header Color
                
                ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,1), (-1,1), 11),
                ('TEXTCOLOR', (0,1), (0,1), colors.HexColor('#3b82f6')),   # Blue for Potential
                ('TEXTCOLOR', (1,1), (1,1), colors.HexColor('#10b981')),   # Green for Collected
                ('TEXTCOLOR', (2,1), (2,1), colors.HexColor('#ef4444')),   # Red for Debt
                
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0'))
            ]))
            elements.append(col_table)
            elements.append(Spacer(1, 15))

            # Historical Growth Section
            if 'history' in router:
                hist = router['history']
                lbls = hist['labels']
                vals = hist['values']
                growth = hist['growth']
                
                # Format growth strings with arrows
                def fmt_growth(g):
                    if g > 0: return f"▲ +{g:.1f}%", colors.HexColor('#10b981') # Green Up
                    if g < 0: return f"▼ {g:.1f}%", colors.HexColor('#ef4444')  # Red Down
                    return "-", colors.grey

                g1_txt, g1_col = fmt_growth(growth[0]) # Current vs Prev 1
                g2_txt, g2_col = fmt_growth(growth[1]) # Prev 1 vs Prev 2

                # Historical Table Data
                # Headers: [Month -2, Month -1, Current Month] (Chronological left to right usually better, or reverse)
                # Let's do: Month -2 -> Month -1 -> Current
                
                hist_data = [
                    ["MES", lbls[2], lbls[1], lbls[0]], # Headers
                    ["RECAUDADO", f"${vals[2]:,.2f}", f"${vals[1]:,.2f}", f"${vals[0]:,.2f}"],
                    ["CRECIMIENTO", "-", g2_txt, g1_txt]
                ]

                hist_table = Table(hist_data, colWidths=[1.5*inch, 2*inch, 2*inch, 2*inch])
                
                # Style needs to apply colors to specific cells for growth
                t_style = [
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), # Header Bold
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8fafc')),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                    ('TEXTCOLOR', (0,1), (-1,1), colors.HexColor('#1e293b')), # Revenue Text
                ]
                
                # Apply colors for growth row
                t_style.append(('TEXTCOLOR', (2,2), (2,2), g2_col))
                t_style.append(('TEXTCOLOR', (3,2), (3,2), g1_col))
                t_style.append(('FONTNAME', (0,2), (-1,2), 'Helvetica-Bold'))

                hist_table.setStyle(TableStyle(t_style))
                
                elements.append(Paragraph("Tendencia de Crecimiento (Últimos 3 Meses)", ParagraphStyle('H3', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=5)))
                elements.append(hist_table)
                elements.append(Spacer(1, 15))
            elements.append(Spacer(1, 15))
            
            # Divider
            elements.append(Paragraph("_" * 60, ParagraphStyle('Divider', parent=styles['Normal'], alignment=1, textColor=colors.lightgrey)))
            elements.append(Spacer(1, 15))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_clients_pdf(clients, router_name="General"):
        """Genera un PDF con el listado de clientes de un router"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                               rightMargin=30, leftMargin=30, 
                               topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        # Premium Title Style
        title_style = ParagraphStyle(
            'PremiumTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#4f46e5'),
            alignment=1,
            spaceAfter=20
        )

        elements.append(Paragraph(f"LISTADO DE CLIENTES - {router_name.upper()}", title_style))
        elements.append(Paragraph(f"Fecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Table Data
        data = [["No.", "CÓDIGO", "NOMBRE", "CÉDULA", "IP", "TELÉFONO"]]
        for i, c in enumerate(clients, 1):
            data.append([
                i,
                c.get('subscriber_code', '-'),
                Paragraph(c.get('legal_name', '-')[:40], styles['Normal']),
                c.get('dni', '-'),
                c.get('ip_address', '-'),
                c.get('phone', '-')
            ])

        # Table Style
        table = Table(data, repeatRows=1, colWidths=[0.5*inch, 1.3*inch, 3.5*inch, 1.4*inch, 1.4*inch, 1.4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
        ]))
        
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_duplicate_ips_report(duplicates_data):
        """Genera un PDF con el reporte de IPs duplicadas"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                               rightMargin=30, leftMargin=30, 
                               topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        # Premium Title Style
        title_style = ParagraphStyle(
            'PremiumTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#ef4444'),
            alignment=1,
            spaceAfter=20
        )
        
        elements.append(Paragraph("REPORTE DE CONFLICTOS DE IP", title_style))
        elements.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        if not duplicates_data:
            elements.append(Paragraph("No se encontraron direcciones IP duplicadas en el sistema.", styles['Normal']))
            doc.build(elements)
            buffer.seek(0)
            return buffer

        # Intro text
        elements.append(Paragraph(f"Se han detectado {len(duplicates_data)} direcciones IP asignadas a múltiples clientes:", styles['Normal']))
        elements.append(Spacer(1, 12))

        for item in duplicates_data:
            ip = item['ip']
            count = item['count']
            clients = item['clients']
            
            # Header for each IP
            elements.append(Paragraph(f"IP: <b>{ip}</b> (Repetida {count} veces)", styles['Heading3']))
            
            # Client Table for this IP
            c_data = [['CÓDIGO', 'NOMBRE', 'ROUTER', 'ESTADO']]
            for c in clients:
                c_data.append([
                    c.get('code', '-'),
                    Paragraph(c.get('name', '-')[:30], styles['Normal']),
                    c.get('router', '-'),
                    c.get('status', '-').upper()
                ])
            
            t = Table(c_data, colWidths=[1.2*inch, 3*inch, 1.5*inch, 1*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 15))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_clients_excel(clients, router_name="General"):
        """Genera un Excel con el listado de clientes de un router"""
        data = []
        for i, c in enumerate(clients, 1):
            data.append({
                'No.': i,
                'Código': c.get('subscriber_code', '-'),
                'Nombre': c.get('legal_name', '-'),
                'Cédula': c.get('dni', '-'),
                'IP': c.get('ip_address', '-'),
                'Teléfono': c.get('phone', '-')
            })
            
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Clientes')
            
            workbook = writer.book
            worksheet = writer.sheets['Clientes']
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4f46e5',
                'font_color': 'white',
                'border': 1
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            worksheet.set_column('C:C', 35) # Nombre
            worksheet.set_column('D:D', 15) # Cédula
            worksheet.set_column('E:E', 15) # IP
                
        buffer.seek(0)
        return buffer
