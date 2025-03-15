import pandas as pd
from io import BytesIO, StringIO
import csv

def export_data(df: pd.DataFrame, format_type: str) -> bytes:
    """
    DataFrame'i belirtilen formatta dışa aktarır
    """
    try:
        # DataFrame'i kopyala
        export_df = df.copy()

        # Boş değerleri temizle
        export_df = export_df.fillna('')

        if format_type == 'csv':
            # CSV dosyasını oluştur
            output = StringIO()
            output.write('\ufeff')  # UTF-8 BOM ekle

            writer = csv.writer(output,
                              quoting=csv.QUOTE_ALL,
                              lineterminator='\r\n')

            # Başlıkları yaz
            writer.writerow(df.columns)

            # Verileri yaz
            for _, row in export_df.iterrows():
                cleaned_row = []
                for val in row:
                    if pd.isna(val):
                        cleaned_row.append('')
                    else:
                        val = str(val).replace('\n', ' ').replace('\r', ' ')
                        val = ' '.join(val.split())
                        cleaned_row.append(val)
                writer.writerow(cleaned_row)

            return output.getvalue().encode('utf-8')

        elif format_type == 'excel':
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Ürünler')
                workbook = writer.book
                worksheet = writer.sheets['Ürünler']

                # Başlık formatı
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#f0f0f0',
                    'border': 1,
                    'text_wrap': True,
                    'align': 'center',
                    'valign': 'vcenter'
                })

                # Sütunları formatla
                for col_num, value in enumerate(export_df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    max_length = max(
                        export_df[value].astype(str).apply(len).max(),
                        len(str(value))
                    )
                    worksheet.set_column(col_num, col_num, min(max_length + 2, 50))

            excel_buffer.seek(0)
            return excel_buffer.getvalue()

        else:
            raise ValueError("Desteklenmeyen format türü")

    except Exception as e:
        raise Exception("Dışa aktarma hatası: %s" % str(e))