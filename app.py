import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Mall HVAC AI Optimizer", layout="wide")

st.title("❄️ High-End Mall Cooling AI Optimizer")
st.write("Predictive HVAC settings based on ECMWF weather data.")

# Open-Meteo ECMWF API endpoint (Coordinates set to Makati City)
@st.cache_data
def get_weather_data():
    url = "https://api.open-meteo.com/v1/ecmwf?latitude=14.55&longitude=121.02&hourly=temperature_2m,relative_humidity_2m&timezone=Asia%2FSingapore"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        return df
    return None

df_weather = get_weather_data()

if df_weather is not None:
    st.subheader("7-Day ECMWF Weather Forecast (Makati)")
    st.line_chart(df_weather.set_index('time')['temperature_2m'])
    
    st.subheader("AI Model Status")
    st.info("Awaiting mall equipment specifications to initialize predictive Chiller/AHU load modeling...")
else:
    st.error("Failed to fetch weather data.")