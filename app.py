import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime

st.set_page_config(page_title="PPM HVAC AI Optimizer", layout="wide")

st.title("Power Plant Mall HVAC Predictive Optimizer")
st.write("Custom operational rules mapped against live ECMWF weather forecasts.")

# 1. Weather Fetch & Wet-Bulb Calculations
def calculate_wet_bulb(t, rh):
    tw = t * np.arctan(0.151977 * (rh + 8.313659)**0.5) + np.arctan(t + rh) - np.arctan(rh - 1.676331) + 0.00391838 * (rh**1.5) * np.arctan(0.023101 * rh) - 4.686035
    return tw

@st.cache_data(ttl="1h")
def get_weather_data():
    url = "https://api.open-meteo.com/v1/ecmwf?latitude=14.56&longitude=121.04&hourly=temperature_2m,relative_humidity_2m&timezone=Asia%2FSingapore"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        df.rename(columns={'temperature_2m': 'temp', 'relative_humidity_2m': 'rh'}, inplace=True)
        # Round decimals to 2 places
        df['wet_bulb'] = calculate_wet_bulb(df['temp'], df['rh']).round(2)
        df['temp'] = df['temp'].round(2)
        return df
    return None

df_weather = get_weather_data()

# ================= SIDEBAR CONTROLS =================
st.sidebar.header("🗓️ Tomorrow's Operational Inputs")
has_event = st.sidebar.checkbox("Event scheduled at 'The Fifth' tomorrow?", value=False)

# Target Tomorrow's Window & Automatically Detect Day of the Week
tomorrow = datetime.date.today() + datetime.timedelta(days=1)
tomorrow_weekday = tomorrow.weekday() # 0 is Monday, 5 is Saturday, 6 is Sunday

# Determine Mall Schedule automatically based on tomorrow's date
if tomorrow_weekday == 5: # Saturday
    day_label = "Saturday"
    mall_open = "10:00 AM"
    reduce_load = "9:00 PM"
elif tomorrow_weekday == 6: # Sunday
    day_label = "Sunday"
    mall_open = "10:00 AM"
    reduce_load = "8:00 PM"
else: # Monday to Friday
    day_label = "Weekday (Mon-Fri)"
    mall_open = "11:00 AM"
    reduce_load = "8:00 PM"

if df_weather is not None:
    df_tomorrow = df_weather[df_weather['time'].dt.date == tomorrow]
    
    if not df_tomorrow.empty:
        peak_temp = df_tomorrow['temp'].max()
        min_wb = df_tomorrow['wet_bulb'].min()
        
        # --- CUSTOM TAILORED RULES ENGINE ---
        if has_event:
            predicted_tr = 3000
            reasoning = "Active event scheduled at 'The Fifth'. Overriding base parameters to handle high occupancy load."
        elif peak_temp < 23.0:
            predicted_tr = 2000
            reasoning = f"Favorable outdoor conditions predicted (Peak: {peak_temp:.2f}°C). Safely scaled down to 2000 TR baseline."
        else:
            predicted_tr = 2500
            reasoning = f"Standard tropical operation profile active. Outdoor peak is {peak_temp:.2f}°C with no events."

        # VFD & Tower Staging Logic Map
        hz_map = {
            2000: {"primary": 45, "secondary": 28, "condenser": 44, "ct_hz": 40, "towers": 4 if min_wb < 24.0 else 5},
            2500: {"primary": 33, "secondary": 28, "condenser": 35, "ct_hz": 40, "towers": 5},
            3000: {"primary": 50, "secondary": 35, "condenser": 50, "ct_hz": 50, "towers": 5}
        }
        
        rec = hz_map[predicted_tr]
        
        # Display Strategy Panels
        st.success(f"### 🎯 Tomorrow's Target Run Profile: {predicted_tr} TR Stage ({tomorrow.strftime('%B %d')})")
        st.caption(f"**AI Strategy Analysis:** {reasoning}")
        
        # Layout Results Blocks
        st.markdown("### ⚙️ Dispatch Schedule Guide & VFD Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📌 **Chiller Startup Sequences ({day_label})**\n"
                    "* **6:30 AM Precooling:** Start **Chiller 2 or Chiller 3** (1000 TR Magnetic Centrifugal).\n"
                    f"* **{mall_open} Mall Opens:** Scale chillers online based on {predicted_tr} TR target.\n"
                    f"* **{reduce_load} Load Reduction:** Drop 1000 TR roughly 1 hour prior to mall close.\n"
                    "* **Closing:** Shutdown plant after cinema/event ends.")
        with col2:
            st.metric("Recommended Active Cooling Towers", f"{rec['towers']} Cells", f"Standard is 5 Cells")
            st.caption(f"Dropping to 4 cells during low wet-bulb hours (below 24.0°C) stops a 55 kW motor completely, maximizing optimization savings. Tomorrow's lowest WB: {min_wb:.2f}°C.")

        st.markdown("#### VFD Setpoint Outputs")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Primary Pumps", f"{rec['primary']} Hz")
        c2.metric("Secondary Pumps", f"{rec['secondary']} Hz")
        c3.metric("Condenser Pumps", f"{rec['condenser']} Hz")
        c4.metric("Cooling Tower Fans", f"{rec['ct_hz']} Hz")

        st.markdown("---")
        st.subheader(f"📊 Tomorrow's Hourly Temperature Profiles (°C) - {tomorrow.strftime('%b %d')}")
        st.line_chart(df_tomorrow.set_index('time')[['temp', 'wet_bulb']])
        
    else:
        st.warning("Weather profile formatting next-day sequence data bounds...")
        
    st.markdown("---")
    st.subheader("🗓️ Continuous 7-Day Context Forecast (°C)")
    st.line_chart(df_weather.set_index('time')['temp'])
else:
    st.error("Unable to capture target forecasting streams from ECMWF servers.")