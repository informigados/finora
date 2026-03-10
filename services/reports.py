from fpdf import FPDF

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'FINORA - Relatório Financeiro', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generate_pdf_report(month, year, finances, stats, output_path=None):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    
    # Period Info
    pdf.cell(0, 10, f'Referência: {month}/{year}', 0, 1, 'L')
    pdf.ln(5)
    
    # Summary Section
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Resumo do Mês', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 12)
    # Simple summary table
    pdf.cell(60, 10, f'Receitas: R$ {stats["total_receitas"]:.2f}', 1)
    pdf.cell(60, 10, f'Despesas: R$ {stats["total_despesas"]:.2f}', 1)
    pdf.cell(60, 10, f'Saldo: R$ {stats["total_geral"]:.2f}', 1)
    pdf.ln(15)
    
    pdf.cell(60, 10, f'Pago: R$ {stats["total_pago"]:.2f}', 1)
    pdf.cell(60, 10, f'Pendente: R$ {stats["total_pendente"]:.2f}', 1)
    pdf.cell(60, 10, f'Atrasado: R$ {stats["total_atrasado"]:.2f}', 1)
    pdf.ln(20)
    
    # Details Table
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Lançamentos', 0, 1, 'L')
    
    pdf.set_font('Arial', 'B', 9)
    # Columns: Date, Desc, Cat, Type, Val, Status
    # Widths: 20, 60, 30, 20, 30, 30 = 190
    col_widths = [20, 60, 30, 20, 30, 30]
    headers = ['Data', 'Descrição', 'Categoria', 'Tipo', 'Valor', 'Status']
    
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font('Arial', '', 9)
    for f in finances:
        # Date
        date_str = f.due_date.strftime('%d/%m')
        pdf.cell(col_widths[0], 8, date_str, 1, 0, 'C')
        
        # Desc (truncate)
        desc = f.description
        if len(desc) > 30: desc = desc[:27] + '...'
        pdf.cell(col_widths[1], 8, desc, 1, 0, 'L')
        
        # Cat
        cat = f.category
        if len(cat) > 15: cat = cat[:12] + '...'
        pdf.cell(col_widths[2], 8, cat, 1, 0, 'L')
        
        # Type
        pdf.cell(col_widths[3], 8, f.type, 1, 0, 'C')
        
        # Value
        pdf.cell(col_widths[4], 8, f'R$ {f.value:.2f}', 1, 0, 'R')
        
        # Status
        pdf.cell(col_widths[5], 8, f.status, 1, 0, 'C')
        
        pdf.ln()
        
    if output_path:
        pdf.output(output_path)
        return output_path

    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode('latin-1')
    return bytes(pdf_bytes)
