import streamlit as st

def apply_custom_styles():
    """Apply enhanced custom styles with modern design elements"""
    st.markdown("""
    <style>
    /* Modern Color Scheme */
    :root {
        --primary-color: #2C3E50;
        --secondary-color: #3498DB;
        --accent-color: #E74C3C;
        --success-color: #2ECC71;
        --warning-color: #F1C40F;
        --background-color: #ECF0F1;
        --card-bg-color: rgba(255, 255, 255, 0.95);
        --text-color: #2C3E50;
    }

    /* Glass Morphism Effect */
    .glass-card {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
    }

    /* Modern Dashboard Layout */
    .stApp {
        background: linear-gradient(135deg, #ECF0F1 0%, #D5DBDB 100%);
        font-family: 'Vazirmatn', sans-serif;
    }

    /* Enhanced Cards */
    div.element-container {
        background: var(--card-bg-color);
        border-radius: 15px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
    }

    div.element-container:hover {
        transform: translateY(-5px);
    }

    /* Animated Metrics */
    [data-testid="stMetric"] {
        background: var(--card-bg-color);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid var(--accent-color);
        animation: slideIn 0.5s ease-out;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-20px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    /* Modern Buttons */
    .stButton > button {
        background: linear-gradient(45deg, var(--primary-color), var(--secondary-color));
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
    }

    /* Enhanced Charts */
    .js-plotly-plot {
        background: var(--card-bg-color);
        border-radius: 15px;
        padding: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    /* Modern Tables */
    .dataframe {
        border: none !important;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .dataframe thead th {
        background-color: var(--primary-color) !important;
        color: white !important;
    }

    .dataframe tbody tr:nth-child(even) {
        background-color: rgba(236, 240, 241, 0.5);
    }

    /* Animated Loading Spinner */
    .stSpinner {
        border: 4px solid var(--background-color);
        border-top: 4px solid var(--accent-color);
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* RTL Support */
    .rtl-content {
        direction: rtl;
        text-align: right;
    }

    /* Responsive Design */
    @media screen and (max-width: 768px) {
        .stButton > button {
            width: 100%;
        }
        
        div.element-container {
            margin: 0.25rem 0;
        }
    }
    </style>
    """, unsafe_allow_html=True)