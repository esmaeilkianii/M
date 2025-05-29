import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import plotly.graph_objects as go
from statsmodels.tsa.seasonal import seasonal_decompose

class TimeSeriesAnalyzer:
    def __init__(self):
        self.prophet_model = Prophet(yearly_seasonality=True, weekly_seasonality=True)
        self.scaler = StandardScaler()
        
    def analyze_trends(self, data, date_column, value_column):
        """Analyze temporal trends in the data"""
        # Prepare data for Prophet
        df = pd.DataFrame({
            'ds': pd.to_datetime(data[date_column]),
            'y': data[value_column]
        })
        
        # Fit Prophet model
        self.prophet_model.fit(df)
        
        # Make future predictions
        future = self.prophet_model.make_future_dataframe(periods=30)
        forecast = self.prophet_model.predict(future)
        
        # Decompose series
        decomposition = seasonal_decompose(df['y'], period=7)
        
        return {
            'forecast': forecast,
            'trend': decomposition.trend,
            'seasonal': decomposition.seasonal,
            'residual': decomposition.resid
        }
    
    def build_lstm_model(self, data, lookback=30):
        """Build and train LSTM model for time series prediction"""
        # Prepare data
        X, y = self._prepare_sequences(data, lookback)
        X = self.scaler.fit_transform(X.reshape(-1, 1)).reshape(X.shape)
        
        # Build model
        model = Sequential([
            LSTM(50, activation='relu', input_shape=(lookback, 1)),
            Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse')
        
        # Train model
        model.fit(X, y, epochs=100, batch_size=32, verbose=0)
        
        return model
    
    def _prepare_sequences(self, data, lookback):
        """Prepare sequences for LSTM"""
        X, y = [], []
        for i in range(len(data) - lookback):
            X.append(data[i:(i + lookback)])
            y.append(data[i + lookback])
        return np.array(X), np.array(y)
    
    def visualize_forecast(self, analysis_results):
        """Create interactive forecast visualization"""
        fig = go.Figure()
        
        # Add actual values
        fig.add_trace(go.Scatter(
            x=analysis_results['forecast']['ds'],
            y=analysis_results['forecast']['y'],
            mode='lines',
            name='Actual'
        ))
        
        # Add forecast
        fig.add_trace(go.Scatter(
            x=analysis_results['forecast']['ds'],
            y=analysis_results['forecast']['yhat'],
            mode='lines',
            name='Forecast',
            line=dict(dash='dash')
        ))
        
        # Add confidence intervals
        fig.add_trace(go.Scatter(
            x=analysis_results['forecast']['ds'],
            y=analysis_results['forecast']['yhat_upper'],
            fill=None,
            mode='lines',
            line=dict(color='rgba(0,100,80,0.2)'),
            name='Upper Bound'
        ))
        
        fig.add_trace(go.Scatter(
            x=analysis_results['forecast']['ds'],
            y=analysis_results['forecast']['yhat_lower'],
            fill='tonexty',
            mode='lines',
            line=dict(color='rgba(0,100,80,0.2)'),
            name='Lower Bound'
        ))
        
        fig.update_layout(
            title='پیش‌بینی روند تغییرات',
            xaxis_title='تاریخ',
            yaxis_title='مقدار',
            hovermode='x unified'
        )
        
        return fig