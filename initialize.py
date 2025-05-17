import streamlit as st
import pandas as pd
import os
import json
import ee

@st.cache_resource
def initialize_app():
    """
    Initialize application resources and authenticate GEE
    """
    # Set up Earth Engine credentials
    try:
        # Try to initialize Earth Engine with service account
        credentials_file = "ee-esmaeilkiani13877-cfdea6eaf411 (4).json"
        if os.path.exists(credentials_file):
            credentials = ee.ServiceAccountCredentials(
                email=None, 
                key_file=credentials_file
            )
            ee.Initialize(credentials)
            st.session_state['ee_initialized'] = True
            return True
        else:
            st.warning(f"فایل اعتبارنامه GEE یافت نشد: {credentials_file}")
            st.session_state['ee_initialized'] = False
            return False
    except Exception as e:
        st.warning(f"خطا در اتصال به Google Earth Engine: {str(e)}")
        st.session_state['ee_initialized'] = False
        return False

@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data():
    """
    Load farm data from CSV files
    """
    try:
        # Try to load farm data from CSV
        farm_csv = "merged_farm_data_renamed (1).csv"
        if os.path.exists(farm_csv):
            df = pd.read_csv(farm_csv)
            return df
        else:
            # Try alternative files
            alt_csv = "cleaned_output.csv"
            if os.path.exists(alt_csv):
                df = pd.read_csv(alt_csv)
                return df
            else:
                st.warning("فایل داده‌های مزارع یافت نشد")
                return pd.DataFrame()  # Return empty dataframe
    except Exception as e:
        st.warning(f"خطا در بارگذاری داده‌های مزارع: {str(e)}")
        return pd.DataFrame()  # Return empty dataframe 