/**
 * AgriCRM Geospatial Tracking Engine
 * Enforces hardware GPS locks and handles permission/secure-context errors visibly.
 */

let map;
let marker;

// Default framework fallbacks (used only as a viewport starting point)
const DEFAULT_LAT = 11.0168;
const DEFAULT_LNG = 76.9558;

function initGeospatialMap() {
    const mapContainer = document.getElementById('map');
    if (!mapContainer) return;

    // 1. Instantly clear the text inputs on load so old data isn't preserved
    clearFormFields();

    // 2. Initialize the map view
    map = L.map('map').setView([DEFAULT_LAT, DEFAULT_LNG], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    marker = L.marker([DEFAULT_LAT, DEFAULT_LNG], { draggable: true }).addTo(map);

    // Watch for manual drag adjustments
    marker.on('dragend', function () {
        const changedCoords = marker.getLatLng();
        synchronizeLocationData(changedCoords.lat, changedCoords.lng);
    });

    // 3. Fire the hardware GPS locator
    triggerLiveLocationTelemetry();
}

function triggerLiveLocationTelemetry() {
    // Check if the current context allows geolocation tracking
    if (!navigator.geolocation) {
        updateStatusUI("❌ Unsupported Browser API");
        alert("Your browser does not support geolocation tracking.");
        return;
    }

    // Check for Secure Context (HTTPS requirement)
    if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        updateStatusUI("❌ Security Error: Requires HTTPS");
        alert("🔒 Geolocation Blocked: Browser security restricts location tracking over insecure HTTP networks. Please use 'localhost' or configure an HTTPS connection.");
        return;
    }

    updateStatusUI("⏳ Locating Satellites...");

    const geoOptions = {
        enableHighAccuracy: true,  // Forces internal phone hardware GPS chips
        timeout: 12000,            // Give up after 12 seconds
        maximumAge: 0              // Don't pull historical cached points
    };

    navigator.geolocation.getCurrentPosition(
        function (position) {
            const freshLat = position.coords.latitude;
            const freshLng = position.coords.longitude;

            console.log(`🛰️ satellite lock achieved: ${freshLat}, ${freshLng}`);

            // Update user map presentation directly to your location in Namakkal
            if (map && marker) {
                marker.setLatLng([freshLat, freshLng]);
                map.setView([freshLat, freshLng], 16);
            }

            // Send true coordinates to reverse geocoder
            synchronizeLocationData(freshLat, freshLng);
        },
        function (error) {
            console.error("GPS hardware block error: ", error);
            handleGeoFailure(error);
        },
        geoOptions
    );
}

function synchronizeLocationData(lat, lng) {
    const latInput = document.getElementById('id_latitude');
    const lngInput = document.getElementById('id_longitude');

    if (latInput) latInput.value = lat.toFixed(6);
    if (lngInput) lngInput.value = lng.toFixed(6);

    // Make sure your backend endpoint reads 'lon' correctly
    fetch(`/crm/api/get-location-details/?lat=${lat}&lon=${lng}`)
        .then(res => {
            if (!res.ok) throw new Error("API Route offline");
            return res.json();
        })
        .then(data => {
            const districtField = document.getElementById('id_district') || document.querySelector('input[name="automated_district"]');
            const areaField = document.getElementById('id_area') || document.querySelector('input[name="automated_area"]');

            if (districtField) districtField.value = data.district || "Unknown District";
            if (areaField) areaField.value = data.area || "Unknown Area";

            updateStatusUI("✅ Location Secured");
        })
        .catch(err => {
            console.error("Reverse lookup failure: ", err);
            updateStatusUI("⚠️ Connection Lookup Fault");
        });
}

function clearFormFields() {
    const districtField = document.getElementById('id_district') || document.querySelector('input[name="automated_district"]');
    const areaField = document.getElementById('id_area') || document.querySelector('input[name="automated_area"]');
    if (districtField) districtField.value = "Detecting current district...";
    if (areaField) areaField.value = "Detecting current area...";
}

function handleGeoFailure(error) {
    let msg = "";
    switch (error.code) {
        case error.PERMISSION_DENIED:
            msg = "❌ Permission Denied: Enable location settings in your browser address bar.";
            break;
        case error.POSITION_UNAVAILABLE:
            msg = "❌ Position Unavailable: Weak GPS signal.";
            break;
        case error.TIMEOUT:
            msg = "❌ Timeout: Request expired before receiving satellite metrics.";
            break;
    }
    updateStatusUI(msg);
    alert(msg);
}

function updateStatusUI(messageString) {
    const badge = document.getElementById('location_status_label') || document.querySelector('.location-secured-badge');
    if (badge) badge.innerText = messageString;
}

document.addEventListener("DOMContentLoaded", function () {
    initGeospatialMap();
});