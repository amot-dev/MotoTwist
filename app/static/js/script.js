// Initialize the map and set its view
const map = L.map('map').setView([49.2827, -123.1207], 9);

// Add a tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

// Object to store the map layers
const mapLayers = {};

// Get the computed styles from the root element (the <html> tag)
const rootStyles = getComputedStyle(document.documentElement);
const accentBlue = rootStyles.getPropertyValue('--accent-blue').trim();
const accentBlueHoverLight = rootStyles.getPropertyValue('--accent-blue-hover-light').trim();
const accentOrange = rootStyles.getPropertyValue('--accent-orange').trim();

const startIcon = new L.Icon({
    iconUrl: '/static/images/marker-icon-green.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize: [19, 31], iconAnchor: [10, 31], shadowSize: [31, 31]
});

const endIcon = new L.Icon({
    iconUrl: '/static/images/marker-icon-red.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize: [19, 31], iconAnchor: [10, 31], shadowSize: [31, 31]
});

const waypointIcon = new L.Icon({
    iconUrl: '/static/images/marker-icon-blue.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize: [19, 31], iconAnchor: [10, 31], shadowSize: [31, 31]
});

/**
 * Loads a Twist's geometry data and adds it to the map as a new layer.
 * @param {string} twistId - The ID of the twist to load.
 * @param {string} twistName - The name of the twist for the popup.
 * @param {boolean} isPaved - Whether the road surface is paved.
 */
async function loadTwistLayer(twistId, twistName, isPaved) {
    // If layer already exists, don't re-load it
    if (mapLayers[twistId]) return;

    // Fetch route data
    try {
        const response = await fetch(`/twists/${twistId}/geometry`);
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        const data = await response.json();

        // Create the route line
        const lineColor = isPaved ? accentBlue : accentOrange;
        const routeLine = L.polyline(data.route_geometry, {
            color: lineColor,
            weight: 5,
            opacity: 0.85
        });
        routeLine.bindPopup(`<b>${twistName}</b>`);

        // Create the waypoint markers
        const waypointMarkers = data.waypoints.map((point, index) => {
            let icon = waypointIcon;
            let zIndexOffset = 0;
            const totalPoints = data.waypoints.length;

            if (totalPoints === 1 || index === 0) icon = startIcon;
            else if (index === totalPoints - 1) icon = endIcon;

            return L.marker(point, { icon: icon, zIndexOffset: zIndexOffset });
        });

        // Group all layers together
        const twistLayer = L.featureGroup([routeLine, ...waypointMarkers]);

        // Store and add the complete layer to the map
        mapLayers[twistId] = twistLayer;
        const twistItem = document.querySelector(`.twist-item[data-twist-id='${twistId}']`);
        if (twistItem && twistItem.classList.contains('is-visible')) {
            twistLayer.addTo(map);
        }

    } catch (error) {
        console.error(`Failed to load route for Twist '${twistName}':`, error);
        flash(`Failed to load route for Twist '${twistName}'`)

        // Ensure a failed layer doesn't stick around
        delete mapLayers[twistId];
    }
}

/**
 * The master function to set the visibility state of a GPX layer and update its UI.
 * This removes duplicated logic from the toggle and restore functions.
 * @param {string} twistId - The ID of the twist to modify.
 * @param {boolean} makeVisible - True to show the layer, false to hide it.
 */
function setLayerVisibility(twistId, makeVisible) {
    const twistItem = document.querySelector(`.twist-item[data-twist-id='${twistId}']`);
    const layer = mapLayers[twistId];

    // Unload if hiding or twist is missing
    if (!makeVisible || !twistItem) {
        if (layer && map.hasLayer(layer)) {
            map.removeLayer(layer);
        }

        // Delete layer and return if twist is missing
        if (!twistItem) {
            delete mapLayers[twistId];
            return;
        }
    }

    // Load layer
    if (makeVisible) {
        if (layer) {
            // Layer is already loaded, just add it back to the map
            layer.addTo(map);
        } else {
            // First time showing this layer, load the GPX data
            const isPaved = twistItem.dataset.paved === 'True';
            const twistName = twistItem.querySelector('.twist-name').textContent;
            loadTwistLayer(twistId, twistName, isPaved);
        }
    }

    // Use the second argument of classList.toggle() to set the state explicitly
    const icon = twistItem.querySelector('.visibility-toggle i');
    twistItem.classList.toggle('is-visible', makeVisible);
    icon.classList.toggle('fa-eye', makeVisible);
    icon.classList.toggle('fa-eye-slash', !makeVisible);

    // Update the saved state
    const visibleItems = document.querySelectorAll('.twist-item.is-visible');
    const visibleIds = Array.from(visibleItems).map(item => item.dataset.twistId);
    localStorage.setItem('visibleTwists', JSON.stringify(visibleIds));
}

/**
 * Iterates over twists in the list and sets their visibility
 * based on what's saved in localStorage.
 */
function applyVisibilityFromStorage() {
    const twistList = document.getElementById('twist-list');
    if (!twistList) return;

    const visibleIdsFromStorage = JSON.parse(localStorage.getItem('visibleTwists')) || [];
    const visibleIdSet = new Set(visibleIdsFromStorage);

    const allTwistItems = twistList.querySelectorAll('.twist-item');
    allTwistItems.forEach(item => {
        const twistId = item.dataset.twistId;
        const shouldBeVisible = visibleIdSet.has(twistId);
        setLayerVisibility(twistId, shouldBeVisible);
    });
}

// Listen for the custom event sent from the server after the twist list is initially loaded
document.body.addEventListener('twistsLoaded', () => {
    applyVisibilityFromStorage();
});

// Listen for the custom event sent from the server after a new twist is created
document.body.addEventListener('twistAdded', (event) => {
    const newTwistId = event.detail.value;
    if (newTwistId) {
        applyVisibilityFromStorage();
        setLayerVisibility(newTwistId, true);
    }
});

// Listen for the custom event sent from the server after a twist is deleted
document.body.addEventListener('twistDeleted', (event) => {
    const deletedTwistId = event.detail.value;
    if (deletedTwistId) {
        applyVisibilityFromStorage();
        setLayerVisibility(deletedTwistId, false);
    }
});

// Listen for clicks on twists
document.getElementById('twist-list').addEventListener('click', function(event) {
    const twistItem = event.target.closest('.twist-item');
    if (!twistItem) return;

    const twistId = twistItem.dataset.twistId;

    if (event.target.closest('.visibility-toggle')) {
        // Clicked on the eye icon
        setLayerVisibility(twistId, !twistItem.classList.contains('is-visible'));
    } else if (event.target.closest('.twist-header')) {
        // Clicked on the twist name
        const ratingDropdown = twistItem.querySelector('.rating-dropdown');
        const isCurrentlyOpen = ratingDropdown.classList.contains('is-open');

        // Hide all rating dropdowns
        const allDropdowns = twistItem.closest('#twist-list').querySelectorAll('.rating-dropdown');
        allDropdowns.forEach(container => {
            container.classList.remove('is-open');
        });

        // Show current rating dropdown if it was hidden
        if (!isCurrentlyOpen) {
            ratingDropdown.classList.add('is-open');

            // Load content if needed
            if (ratingDropdown.querySelector('.loading')) {
                const twistHeader = twistItem.querySelector('.twist-header')
                htmx.trigger(twistHeader, 'load-ratings');
            }
        }

        // Pan and zoom the map
        const layer = mapLayers[twistId];
        if (layer) {
            // If bounds are already available, use them. Otherwise, wait for the 'loaded' event
            if (layer.getBounds().isValid()) {
                map.fitBounds(layer.getBounds());
            } else {
                layer.on('loaded', (e) => map.fitBounds(e.target.getBounds()));
            }
        }
    }
});


const createTwistButton = document.querySelector('#start-new-twist');
const finalizeTwistButton = document.querySelector('#finalize-new-twist')
const cancelTwistButton = document.querySelector('#cancel-new-twist')
const mapContainer = document.querySelector('#map');
const twistForm = document.querySelector('#modal-create-twist form');
let waypointCoords = [];
let waypointMarkers = [];
let routeLine = null;

// Update marker icons based off position in list
function updateMarkerIcons() {
    const totalMarkers = waypointMarkers.length;
    waypointMarkers.forEach((marker, index) => {
        if (totalMarkers === 1 || index === 0) {
            marker.setIcon(startIcon);
        } else if (index === totalMarkers - 1) {
            marker.setIcon(endIcon);
        } else {
            marker.setIcon(waypointIcon);
        }
    });
}

/**
 * Handles creation of the route line while a Twist is being created.
 */
async function updateRoute() {
    if (routeLine) map.removeLayer(routeLine);

    if (waypointCoords.length < 2) return;

    // Format coordinates and call the OSRM API
    const coordinates = waypointCoords.map(coord => `${coord.lng},${coord.lat}`).join(';');
    const url = `http://router.project-osrm.org/route/v1/driving/${coordinates}?overview=full&geometries=geojson`;

    // TODO: cancel request on new one
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Route not found');

        const data = await response.json();
        const routeGeometry = data.routes[0].geometry.coordinates;

        // OSRM returns [lng, lat], Leaflet needs [lat, lng]
        const latLngs = routeGeometry.map(coord => [coord[1], coord[0]]);

        // Create a new polyline and add it to the map
        routeLine = L.polyline(latLngs, { color: accentBlueHoverLight }).addTo(map);
    } catch (error) {
        console.error("Error fetching route:", error);
        flash("Error drawing route", 5000, backgroundColor=accentOrange);
    }
}

function stopTwistCreation() {
    waypointMarkers.forEach(marker => map.removeLayer(marker));
    waypointCoords = [];
    waypointMarkers = [];

    if (routeLine) {
        map.removeLayer(routeLine);
        routeLine = null;
    }

    // Reset the status indicator
    const statusIndicator = document.querySelector('#route-status-indicator');
    statusIndicator.classList.add('gone');
    statusIndicator.textContent = '';

    // Reset button visibility to the initial state
    finalizeTwistButton.classList.add('gone');
    cancelTwistButton.classList.add('gone');
    createTwistButton.classList.remove('gone');
}

// Begin recording route geometry
createTwistButton.addEventListener('click', () => {
    mapContainer.classList.add('creating-twist');
    flash('Click on the map to create a Twist!', 5000);

    // Swap button visibility
    createTwistButton.classList.add('gone');
    finalizeTwistButton.classList.remove('gone');
    cancelTwistButton.classList.remove('gone');
});

// Handle saving of route geometry
finalizeTwistButton.addEventListener('click', () => {
    mapContainer.classList.remove('creating-twist');

    const statusIndicator = document.querySelector('#route-status-indicator');

    // Check if there's a route to save
    if (waypointCoords.length > 1 && routeLine) {
        const waypointsForJson = waypointCoords.map(coord => ({ lat: coord.lat, lng: coord.lng }));
        document.querySelector('#waypoints-data').value = JSON.stringify(waypointsForJson);

        const routeLatLngs = routeLine.getLatLngs();
        const routeForJson = routeLatLngs.map(coord => ({ lat: coord.lat, lng: coord.lng }));
        document.querySelector('#route-geometry-data').value = JSON.stringify(routeForJson);

        statusIndicator.textContent = `✅ Route captured with ${waypointCoords.length} waypoints and ${routeLatLngs.length} geometry points.`;
        statusIndicator.classList.remove('gone');

    } else {
        // Handle case where user finalizes without a valid route
        statusIndicator.textContent = '⚠️ No valid route was created.';
        statusIndicator.classList.remove('gone');
    }
});

// Handle cancellation of route geometry recording
cancelTwistButton.addEventListener('click', () => {
    mapContainer.classList.remove('creating-twist');
    stopTwistCreation();
});

// Listen for map clicks when recording route geometry
map.on('click', function(e) {
    if (!mapContainer.classList.contains('creating-twist')) return;

    // Create a new marker
    const marker = L.marker(e.latlng, { draggable: true }).addTo(map); // TODO: draggable

    // Add a click listener to the marker to remove it
    marker.on('click', () => {
        const index = waypointMarkers.indexOf(marker);
        if (index > -1) {
            // Remove from map and arrays using the index
            map.removeLayer(waypointMarkers[index]);
            waypointMarkers.splice(index, 1);
            waypointCoords.splice(index, 1);

            // Update the route line with the modified waypoint list
            updateRoute();
            updateMarkerIcons();
        }
    });

    // Listen for the marker being dragged and update route on end
    marker.on('dragend', (event) => {
        const index = waypointMarkers.indexOf(marker);
        if (index > -1) {
            // Redraw the route with the new coordinates
            waypointCoords[index] = event.target.getLatLng();
            updateRoute();
        }
    });

    // Add the new waypoint and marker to state arrays
    waypointCoords.push(e.latlng);
    waypointMarkers.push(marker);

    // Update the route line with the new waypoint
    updateRoute();
    updateMarkerIcons();
});

// HTMX hook for cleanup
// TODO: make this more specific
twistForm.addEventListener('htmx:afterRequest', function() {
    setTimeout(() => {
        stopTwistCreation();
    }, 100);
});