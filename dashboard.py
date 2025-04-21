import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from plotly.subplots import make_subplots

# تنظیمات صفحه
st.set_page_config(
    page_title="داشبورد تحلیلی نیشکر",
    page_icon="🌾",
    layout="wide"
)

# استایل سفارشی
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        
        .main {
            font-family: 'Vazirmatn', sans-serif;
        }
        
        .card {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin: 10px 0;
            transition: transform 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
        }
        
        .metric-card {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            border-radius: 15px;
            padding: 20px;
            margin: 10px 0;
        }
        
        .chart-container {
            background-color: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            margin: 10px 0;
        }
    </style>
""", unsafe_allow_html=True)

# خواندن داده‌ها
@st.cache_data
def load_data():
    df = pd.read_csv('محاسبات 2.csv')
    return df

df = load_data()

# عنوان اصلی
st.title("🌾 داشبورد تحلیلی نیشکر")

# ایجاد کارت‌های متریک
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
        <div class="metric-card">
            <h3>کل مساحت (هکتار)</h3>
            <h2>9,421.30</h2>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <div class="metric-card">
            <h3>تعداد واریته‌ها</h3>
            <h2>9</h2>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
        <div class="metric-card">
            <h3>تعداد ادارات</h3>
            <h2>4</h2>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
        <div class="metric-card">
            <h3>تعداد سن‌ها</h3>
            <h2>9</h2>
        </div>
    """, unsafe_allow_html=True)

# نمودار سه بعدی مساحت به تفکیک اداره، سن و واریته
st.markdown("""
    <div class="chart-container">
        <h3>نمودار سه بعدی مساحت به تفکیک اداره، سن و واریته</h3>
    </div>
""", unsafe_allow_html=True)

# پردازش داده‌ها برای نمودار سه بعدی
def prepare_3d_data(df):
    # تبدیل داده‌ها به فرمت مناسب برای نمودار سه بعدی
    data = []
    for _, row in df.iterrows():
        if row['اداره'] != 'Grand Total' and row['سن'] != 'total':
            for col in ['CP69', 'CP73', 'CP48', 'CP57', 'CP65', 'CP70', 'IR01-412', 'IRC99-07', 'IRC00-14']:
                if pd.notna(row[col]) and row[col] != 0:
                    data.append({
                        'اداره': row['اداره'],
                        'سن': row['سن'],
                        'واریته': col,
                        'مساحت': row[col]
                    })
    return pd.DataFrame(data)

df_3d = prepare_3d_data(df)

# ایجاد نمودار سه بعدی
fig = go.Figure(data=[go.Scatter3d(
    x=df_3d['اداره'],
    y=df_3d['سن'],
    z=df_3d['مساحت'],
    mode='markers',
    marker=dict(
        size=df_3d['مساحت']/10,
        color=df_3d['مساحت'],
        colorscale='Viridis',
        opacity=0.8
    ),
    text=df_3d['واریته'],
    hovertemplate="اداره: %{x}<br>سن: %{y}<br>مساحت: %{z:.2f} هکتار<br>واریته: %{text}<extra></extra>"
)])

fig.update_layout(
    scene = dict(
        xaxis_title="اداره",
        yaxis_title="سن",
        zaxis_title="مساحت (هکتار)"
    ),
    margin=dict(l=0, r=0, b=0, t=30),
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# نمودار هیستوگرام سورفیس
st.markdown("""
    <div class="chart-container">
        <h3>هیستوگرام سورفیس مساحت به تفکیک اداره و سن</h3>
    </div>
""", unsafe_allow_html=True)

# پردازش داده‌ها برای هیستوگرام سورفیس
def prepare_surface_data(df):
    data = []
    for _, row in df.iterrows():
        if row['اداره'] != 'Grand Total' and row['سن'] != 'total':
            data.append({
                'اداره': row['اداره'],
                'سن': row['سن'],
                'مساحت': row['Grand Total']
            })
    return pd.DataFrame(data)

df_surface = prepare_surface_data(df)

# ایجاد هیستوگرام سورفیس
fig_surface = go.Figure(data=[go.Surface(
    x=df_surface['اداره'].unique(),
    y=df_surface['سن'].unique(),
    z=df_surface.pivot(index='سن', columns='اداره', values='مساحت').values
)])

fig_surface.update_layout(
    scene = dict(
        xaxis_title="اداره",
        yaxis_title="سن",
        zaxis_title="مساحت (هکتار)"
    ),
    margin=dict(l=0, r=0, b=0, t=30),
    height=600
)

st.plotly_chart(fig_surface, use_container_width=True)

# نمودار مقایسه‌ای واریته‌ها
st.markdown("""
    <div class="chart-container">
        <h3>مقایسه واریته‌ها در ادارات مختلف</h3>
    </div>
""", unsafe_allow_html=True)

# پردازش داده‌ها برای نمودار مقایسه‌ای
varieties = ['CP69', 'CP73', 'CP48', 'CP57', 'CP65', 'CP70', 'IR01-412', 'IRC99-07', 'IRC00-14']
fig_varieties = go.Figure()

for variety in varieties:
    data = df[df['اداره'] != 'Grand Total'].groupby('اداره')[variety].sum()
    fig_varieties.add_trace(go.Bar(
        name=variety,
        x=data.index,
        y=data.values
    ))

fig_varieties.update_layout(
    barmode='group',
    xaxis_title="اداره",
    yaxis_title="مساحت (هکتار)",
    height=400
)

st.plotly_chart(fig_varieties, use_container_width=True) 