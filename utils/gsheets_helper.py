import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

class GSheetsHelper:
    def __init__(self, creds_path, sheet_id, worksheet_index=0):
        # Define the scope
        self.scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        # Authorize the client
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, self.scope)
        self.client = gspread.authorize(self.creds)
        # Open the sheet
        self.sheet = self.client.open_by_key(sheet_id)
        self.worksheet = self.sheet.get_worksheet(worksheet_index)

    def get_all_records(self):
        """Return all rows as a list of dicts."""
        return self.worksheet.get_all_records()

    def get_unprocessed_rows(self, processed_col='Processed'):
        """Return (row_index, row_dict) for each row where 'Processed' is empty."""
        records = self.get_all_records()
        unprocessed = []
        for idx, row in enumerate(records):
            if processed_col not in row or not row[processed_col]:
                unprocessed.append((idx + 2, row))  # +2: 1 for header, 1 for 1-based index
        return unprocessed

    def update_prediction(self, row_index, prediction, processed_col='Processed', prediction_col='Prediction'):
        """Update the prediction and mark as processed for a given row index (1-based)."""
        # Find column numbers
        header = self.worksheet.row_values(1)
        pred_col_num = header.index(prediction_col) + 1 if prediction_col in header else len(header) + 1
        proc_col_num = header.index(processed_col) + 1 if processed_col in header else len(header) + 2

        # Write prediction
        self.worksheet.update_cell(row_index, pred_col_num, prediction)
        # Mark as processed
        from datetime import datetime
        self.worksheet.update_cell(row_index, proc_col_num, f"Processed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def append_prediction_column(self, prediction_col='Prediction', processed_col='Processed'):
        """Add 'Prediction' and 'Processed' columns if not present."""
        header = self.worksheet.row_values(1)
        updates = False
        if prediction_col not in header:
            self.worksheet.update_cell(1, len(header) + 1, prediction_col)
            updates = True
        if processed_col not in header:
            self.worksheet.update_cell(1, len(header) + (2 if not updates else 1), processed_col)

