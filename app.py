import os
import time
import gspread
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from schedule import every, run_pending

# Load environment variables
load_dotenv()

class PestDetectionSystem:
    def __init__(self):
        self.model = joblib.load('models/pest_detector_model.pkl')
        self.scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(
            'config/credentials.json', self.scope)
        self.client = gspread.authorize(self.creds)
        self.sheet = self.client.open_by_key(os.getenv('SHEET_ID')).sheet1

    def _preprocess_data(self, row):
        """Convert sheet row to model input format"""
        return np.array([
            float(row[1]),  # Moisture_Sensor
            float(row[2]),  # Humidity
            float(row[3]),  # Temperature
            float(row[4]),  # Infrared_Sensor
            float(row[5]),  # Motion_Sensor
            float(row[6]),  # Vibration_Sensor
            float(row[7])   # Gas_Sensor
        ]).reshape(1, -1)

    def process_new_entries(self):
        """Check for new rows and make predictions"""
        records = self.sheet.get_all_records()
        df = pd.DataFrame(records)
        
        if 'Prediction' not in df.columns:
            self.sheet.insert_cols([['Prediction']], len(df.columns)+1)
            self.sheet.insert_cols([['Processed']], len(df.columns)+1)
            time.sleep(2)  # Wait for sheet update
            return

        unprocessed = df[df['Processed'].astype(str) == '']
        
        for idx in unprocessed.index:
            row_num = idx + 2  # Sheets are 1-indexed + header row
            try:
                row_data = self.sheet.row_values(row_num)
                features = self._preprocess_data(row_data)
                prediction = self.model.predict(features)[0]
                confidence = self.model.predict_proba(features)[0][1]
                
                # Update prediction and processing status
                self.sheet.update_cell(row_num, len(row_data)+1, 
                    'Pest Detected' if prediction == 1 else 'No Pest')
                self.sheet.update_cell(row_num, len(row_data)+2, 
                    f'Processed at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
                
            except Exception as e:
                print(f"Error processing row {row_num}: {e}")
                self.sheet.update_cell(row_num, len(row_data)+2, f'Error: {str(e)}')

if __name__ == "__main__":
    system = PestDetectionSystem()
    
    # Run every 5 minutes
    every(5).minutes.do(system.process_new_entries)
    
    print("🚀 Pest Detection System Started")
    while True:
        run_pending()
        time.sleep(1)
