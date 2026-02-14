import streamlit as st
import pandas as pd
import requests
from math import radians, sin, cos, sqrt, atan2

DATA_FILE = "uk_cinemas_clean.csv"
POSTCODE_API = "https://api.postcodes.io/postcodes/{}"
EARTH_RADIUS_KM = 6371.0

st.set_page_config(page_title="UK Cinema Finder", page_icon="🎬", layout="wide")


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = ["name", "city", "brand", "operator", "latitude", "longitude"]
    df = df[cols].copy()
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    return df


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def geocode_postcode(postcode: str):
    cleaned = postcode.strip().upper().replace(" ", "")
    if not cleaned:
        return None, None, "Please enter a postcode."

    url = POSTCODE_API.format(cleaned)
    r = requests.get(url, timeout=10)

    if r.status_code != 200:
        return None, None, "Postcode lookup failed. Try again."

    data = r.json()
    if data.get("status") != 200 or data.get("result") is None:
        return None, None, "Invalid postcode. Please try a valid UK postcode."

    return float(data["result"]["latitude"]), float(data["result"]["longitude"]), None


st.title("🎬 UK Cinema Finder")
st.caption("Find the nearest UK cinemas to any postcode using OpenStreetMap data + straight-line (Haversine) distance.")

df = load_data(DATA_FILE)

left, right = st.columns([1, 1])

with left:
    postcode = st.text_input("Enter a UK postcode", placeholder="e.g., SW1A 1AA")
    max_km = st.slider("Maximum distance (km)", min_value=1, max_value=50, value=10)
    n = st.selectbox("Number of cinemas to show", [5, 10, 15, 20], index=1)
    run = st.button("Find cinemas")

with right:
    st.write("**Dataset**:", len(df), "cinema locations")
    st.info("Distances are straight-line ('as-the-crow-flies'), not road travel distance.")

if run:
    user_lat, user_lon, err = geocode_postcode(postcode)
    if err:
        st.error(err)
        st.stop()

    st.success(f"📍 Coordinates found: {user_lat:.6f}, {user_lon:.6f}")

    work = df.copy()
    work["distance_km"] = work.apply(
        lambda row: haversine_km(user_lat, user_lon, row["latitude"], row["longitude"]),
        axis=1
    )

    work = work[work["distance_km"] <= max_km].sort_values("distance_km").head(n).copy()
    work["distance_km"] = work["distance_km"].round(2)

    if work.empty:
        st.warning(f"No cinemas found within {max_km} km. Try increasing the distance.")
        st.stop()

    map_df = pd.DataFrame({
        "lat": [user_lat] + work["latitude"].tolist(),
        "lon": [user_lon] + work["longitude"].tolist()
    })

    c1, c2 = st.columns([1, 1])

    with c1:
        st.subheader("Nearest cinemas")
        st.dataframe(
            work[["name", "city", "brand", "operator", "distance_km"]],
            use_container_width=True
        )

        csv_bytes = work.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download results as CSV",
            data=csv_bytes,
            file_name="nearest_cinemas.csv",
            mime="text/csv"
        )

    with c2:
        st.subheader("Map")
        st.map(map_df, zoom=11)
