import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def update_farm_data(input_csv: str, output_csv: str):
    """
    Update farm data with sugarcane-specific information
    """
    # Read the input CSV
    df = pd.read_csv(input_csv)
    
    # Add sugarcane-specific columns if they don't exist
    if 'age_days' not in df.columns:
        # Calculate age in days (assuming planting date is in a column named 'planting_date')
        if 'planting_date' in df.columns:
            df['planting_date'] = pd.to_datetime(df['planting_date'])
            df['age_days'] = (datetime.now() - df['planting_date']).dt.days
        else:
            # If no planting date, use a default age based on growth stage
            df['age_days'] = np.random.randint(30, 300, size=len(df))
    
    if 'area_hectares' not in df.columns:
        # Add area information if not present
        df['area_hectares'] = np.random.uniform(10, 100, size=len(df))
    
    if 'temperature' not in df.columns:
        # Add temperature data (can be updated with real data)
        df['temperature'] = np.random.uniform(20, 35, size=len(df))
    
    if 'et0' not in df.columns:
        # Add reference evapotranspiration (can be updated with real data)
        df['et0'] = np.random.uniform(4, 8, size=len(df))
    
    # Add previous NDVI and days since last measurement for growth rate calculation
    if 'previous_ndvi' not in df.columns:
        df['previous_ndvi'] = df['NDVI'] - np.random.uniform(0.05, 0.15, size=len(df))
        df['days_since_last_measurement'] = np.random.randint(7, 14, size=len(df))
    
    # Save the updated dataframe
    df.to_csv(output_csv, index=False)
    print(f"Updated farm data saved to {output_csv}")

if __name__ == "__main__":
    update_farm_data('cleaned_output.csv', 'updated_farm_data.csv') 