import streamlit as st
import pandas as pd

def render_sidebar(farm_data_df):
    """
    Renders the sidebar with filters and returns the selected filter values
    """
    st.sidebar.title("سامانه پایش هوشمند نیشکر")
    st.sidebar.image("logo.app.png", width=150)
    
    # Initialize filters
    filters = {}
    
    # Add filters based on farm data
    if not farm_data_df.empty:
        # Date range filter
        st.sidebar.subheader("انتخاب بازه زمانی")
        
        # Get min and max dates from data if available
        try:
            min_date = pd.to_datetime("2023-01-01")
            max_date = pd.to_datetime("2023-12-31")
            
            filters['start_date'] = st.sidebar.date_input(
                "از تاریخ",
                min_date,
                min_value=min_date,
                max_value=max_date
            )
            
            filters['end_date'] = st.sidebar.date_input(
                "تا تاریخ",
                max_date,
                min_value=filters['start_date'],
                max_value=max_date
            )
        except:
            st.sidebar.warning("خطا در تنظیم بازه زمانی")
        
        # Farm selection filter
        st.sidebar.subheader("انتخاب مزرعه")
        
        if 'farm_name' in farm_data_df.columns:
            unique_farms = sorted(farm_data_df['farm_name'].unique())
            filters['selected_farm'] = st.sidebar.selectbox(
                "نام مزرعه",
                options=unique_farms
            )
        elif 'name' in farm_data_df.columns:
            unique_farms = sorted(farm_data_df['name'].unique())
            filters['selected_farm'] = st.sidebar.selectbox(
                "نام مزرعه",
                options=unique_farms
            )
        else:
            st.sidebar.warning("ستون نام مزرعه یافت نشد")
    
    # Theme selection
    st.sidebar.subheader("تنظیمات ظاهری")
    if 'selected_theme_name' in st.session_state:
        theme_options = ["پیش‌فرض (آبی تیره)", "تم سبز (طبیعت)", "تم قرمز (هشدار)", "تم زرد/نارنجی (گرم)", "تم قهوه‌ای (خاکی)", "تم روشن (ساده)"]
        selected_theme = st.sidebar.selectbox(
            "انتخاب تم",
            options=theme_options,
            index=theme_options.index(st.session_state.selected_theme_name)
        )
        
        if selected_theme != st.session_state.selected_theme_name:
            st.session_state.selected_theme_name = selected_theme
            st.rerun()
    
    return filters 