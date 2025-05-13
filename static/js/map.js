// map.js

let map; // Global map variable

// Initialize the Leaflet Map
function initMap() {
    map = L.map('customer-map').setView([40.7128, -74.0060], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}

function loadGeoJsonData(geojsonData) {
    L.geoJSON(geojsonData, {
        style: function(feature) {
            // Simplified style for polygons
            return { color: "#ff7800", weight: 2, opacity: 1 };
        },
        onEachFeature: function(feature, layer) {
            // Customize popup content based on available properties
            let popupContent = '';
            if (feature.properties) {
                if (feature.properties['city']) {
                    popupContent += `City: ${feature.properties['city']}<br>`;
                }
                if (feature.properties['postal-code']) {
                    popupContent += `Postal Code: ${feature.properties['postal-code']}<br>`;
                }
                // Add more properties as needed
            }
            layer.bindPopup(popupContent);
        }
        // Removed pointToLayer and filter as they may not be needed
    }).addTo(map);
}


// Export functions if using modules
export { initMap, loadGeoJsonData };
