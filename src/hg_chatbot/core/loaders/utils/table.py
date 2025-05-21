import io
import openpyxl

from typing import BinaryIO, IO

def get_visible_sheets(file):
        """Get list of visible sheets from Excel file."""
        if isinstance(file, (io.BytesIO, BinaryIO, IO)):
            try:
                current_position = file.tell()
                file.seek(0)
                wb = openpyxl.load_workbook(file, read_only=True)
                file.seek(current_position)
            except Exception as e:
                raise ValueError(f"Error reading Excel file: {str(e)}")
        else:
            try:
                wb = openpyxl.load_workbook(file, read_only=True)
            except Exception as e:
                raise ValueError(f"Error reading Excel file: {str(e)}")

        visible_sheets = [sheet.title for sheet in wb.worksheets if not sheet.sheet_state == 'hidden']
        return visible_sheets
