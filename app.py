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
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading

# Load environment variables
load_dotenv()

app = FastAPI(title="Pest Detection API")

class SensorData(BaseModel):
    Moisture_Sensor: float
    Humidity: float
    Temperature: float
    Infrared_Sensor: float
    Motion_Sensor: float
    Vibration_Sensor: float
    Gas_Sensor: float

class PestDetectionSystem:
    def __init__(self):
        # Load ML model with absolute path
        self.model = self.load_model(
            os.path.join(os.path.dirname(__file__), 'models', 'pest_detector_model_2.pkl')
        )
        
        # Initialize Google Sheets connection
        self.scope = ['https://spreadsheets.google.com/feeds',
                      'https://www.googleapis.com/auth/drive']
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(
            os.path.join(os.path.dirname(__file__), 'config', 'credentials.json'), 
            self.scope
        )
        self.client = gspread.authorize(self.creds)
        self.sheet = self.client.open_by_key(os.getenv('SHEET_ID')).sheet1

    def load_model(self, model_path):
        try:
            return joblib.load(model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {str(e)}")

    def process_new_entries(self):
        try:
            records = self.sheet.get_all_records()
            df = pd.DataFrame(records)
            self.ensure_columns_exist()
            unprocessed = df[df['Processed'].astype(str) == '']
            for idx in unprocessed.index:
                self.process_row(idx + 2)
        except Exception as e:
            print(f"Processing error: {str(e)}")

    def ensure_columns_exist(self):
        header = self.sheet.row_values(1)
        required_cols = ['Processed', 'Prediction']
        updates = False
        for col in required_cols:
            if col not in header:
                self.sheet.insert_cols([col], len(header) + 1)
                header.append(col)
                updates = True
                time.sleep(1)
        if updates:
            print("Added missing columns")

    def process_row(self, row_num):
        try:
            row_data = self.sheet.row_values(row_num)
            features = self.extract_features(row_data)
            if not features:
                self.mark_processed(row_num, "Invalid data")
                return
            prediction = self.model.predict([features])[0]
            confidence = self.get_confidence(features)
            self.update_sheet(row_num, prediction, confidence)
        except Exception as e:
            self.mark_processed(row_num, f"Error: {str(e)}")
            print(f"Row {row_num} error: {str(e)}")

    def extract_features(self, row_data):
        try:
            return [
                float(row_data[1]),
                float(row_data[2]),
                float(row_data[3]),
                float(row_data[4]),
                float(row_data[5]),
                float(row_data[6]),
                float(row_data[7])
            ]
        except (IndexError, ValueError):
            return None

    def get_confidence(self, features):
        if hasattr(self.model, 'predict_proba'):
            return round(100 * max(self.model.predict_proba([features])[0]), 2)
        return None

    def update_sheet(self, row_num, prediction, confidence):
        prediction_text = f"{'Pest Detected' if prediction == 1 else 'No Pest'}"
        if confidence:
            prediction_text += f" ({confidence}%)"
        self.sheet.update_cell(row_num, 9, prediction_text)
        self.mark_processed(row_num)

    def mark_processed(self, row_num, message=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = message or f"Processed at {timestamp}"
        self.sheet.update_cell(row_num, 10, status)

    def predict_from_input(self, data: SensorData):
        features = [
            data.Moisture_Sensor,
            data.Humidity,
            data.Temperature,
            data.Infrared_Sensor,
            data.Motion_Sensor,
            data.Vibration_Sensor,
            data.Gas_Sensor
        ]
        prediction = self.model.predict([features])[0]
        confidence = self.get_confidence(features)
        return prediction, confidence


# Instantiate system
system = PestDetectionSystem()

@app.get("/")
def root():
    return {"message": "Pest Detection API is running 🚀"}

@app.post("/predict")
def predict(data: SensorData):
    try:
        prediction, confidence = system.predict_from_input(data)
        return {
            "prediction": "Pest Detected" if prediction == 1 else "No Pest",
            "confidence": f"{confidence}%" if confidence is not None else "N/A"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Background job to keep running every 2 minutes
def schedule_loop():
    print("✅ Background scheduler started")
    every(2).minutes.do(system.process_new_entries)
    while True:
        run_pending()
        time.sleep(1)

# Start background thread on app startup
@app.on_event("startup")
def start_background():
    thread = threading.Thread(target=schedule_loop, daemon=True)
    thread.start()
