/* Map Display */

// Initialize the map and set its view
const map = L.map('map').setView([49.2827, -123.1207], 9);

// Try to locate the user
document.addEventListener('DOMContentLoaded', () => {
    map.locate({ setView: true, maxZoom: 9 });
});

// Add a tile layer
L.tileLayer(OSM_URL, {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

// Object to store the map layers
const mapLayers = {};

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

const hiddenIcon = new L.Icon({
    iconUrl: '/static/images/marker-icon-grey.png',
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
            const totalPoints = data.waypoints.length;

            if (totalPoints === 1 || index === 0) icon = startIcon;
            else if (index === totalPoints - 1) icon = endIcon;

            return L.marker(point, { icon: icon })
                .bindPopup(`<b>${twistName}</b>${point.name ? `<br>${point.name}` : ''}`);
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


// Listen for the custom event sent from the server when a modal needs to be closed
document.body.addEventListener('closeModal', () => {
    location.hash='';
    forms = document.querySelectorAll('form')
    forms.forEach(form => form.reset());
    stopTwistCreation();
});

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
        const ratingsDropdown = twistItem.querySelector('.ratings-dropdown');
        const isCurrentlyOpen = ratingsDropdown.classList.contains('is-open');

        // Hide all rating dropdowns
        const allRatingsDropdowns = twistItem.closest('#twist-list').querySelectorAll('.ratings-dropdown');
        allRatingsDropdowns.forEach(container => {
            container.classList.remove('is-open');
        });

        // Show current rating dropdown if it was hidden
        if (!isCurrentlyOpen) {
            ratingsDropdown.classList.add('is-open');

            // Load content if needed
            if (ratingsDropdown.querySelector('.loading')) {
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
                layer.on('loaded', (event) => map.fitBounds(event.target.getBounds()));
            }
        }
    }
});

/* New Twist Creation */
const createTwistButton = document.querySelector('#start-new-twist');
const finalizeTwistButton = document.querySelector('#finalize-new-twist')
const cancelTwistButton = document.querySelector('#cancel-new-twist')
const mapContainer = document.querySelector('#map');
const createWaypointPopupTemplate = document.querySelector('#create-waypoint-popup-template').content;
const twistForm = document.querySelector('#modal-create-twist form');

// State Variables
let waypoints = [];
let waypointMarkers = [];
let routeRequestController;
let newRouteLine = null;

/**
 * Updates a container element with a new message paragraph.
 * @param {HTMLElement} element The container element to update.
 * @param {string} message The text content for the new paragraph.
 * @param {'w' | 'a'} mode 'w' to write (overwrite), 'a' to append. Defaults to 'w'.
 */
function writeToStatus(element, message, mode = 'w') {
    // If mode is 'write', clear the container first.
    if (mode === 'w') {
    element.innerHTML = '';
    }

    // Create a new paragraph, set its text, and append it.
    const p = document.createElement('p');
    p.textContent = message;
    element.appendChild(p);
}

/**
 * Sets the visibility icon for a waypoint's hide button based on its isHidden property.
 * @param {object} waypoint The waypoint object.
 * @param {HTMLElement} hideIcon The <i> element for the icon.
 */
function configureHiddenWaypointPopup(waypoint, hideIcon, nameInput) {
    if (waypoint.isHidden) {
        hideIcon.classList.remove('fa-solid');
        hideIcon.classList.add('fa-regular');

        // Disable the input and set its text
        nameInput.disabled = true;
        nameInput.value = 'Shaping Point';
    } else {
        hideIcon.classList.remove('fa-regular');
        hideIcon.classList.add('fa-solid');

        // Re-enable the input and restore its original name (if any)
        nameInput.disabled = false;
        nameInput.value = waypoint.name;
    }
}

/**
 * Creates and configures the DOM element for a marker's popup.
 * @param {L.Marker} marker The marker for which to create the popup content.
 * @returns {HTMLElement} The configured popup content element.
 */
function createPopupContent(marker) {
    const index = waypointMarkers.indexOf(marker);
    if (index === -1) return null;

    const waypoint = waypoints[index];
    const totalMarkers = waypointMarkers.length;

    // Create a fresh clone of the template
    const popupContent = createWaypointPopupTemplate.cloneNode(true);
    const nameInput = popupContent.querySelector('.create-waypoint-name-input');
    const hideButton = popupContent.querySelector('.popup-button-hide');
    const hideIcon = hideButton.querySelector('i');
    const deleteButton = popupContent.querySelector('.popup-button-delete');

    // Input for the waypoint name
    nameInput.value = waypoint.name;
    nameInput.addEventListener('input', (event) => {
        waypoint.name = event.target.value; // Persist name change
    });

    // Close popup on enter
    nameInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            map.closePopup();
        }
    });

    // Toggle visibility of the hide button for start/end markers
    const isStart = index === 0;
    const isEnd = index === totalMarkers - 1 && totalMarkers > 1;
    hideButton.classList.toggle('gone', isStart || isEnd);

    configureHiddenWaypointPopup(waypoint, hideIcon, nameInput)

    // Hide button
    hideButton.addEventListener('click', () => {
        waypoint.isHidden = !waypoint.isHidden;
        configureHiddenWaypointPopup(waypoint, hideIcon, nameInput)
        updateMarkerIcons();
    });

    // Delete button
    deleteButton.addEventListener('click', () => {
        const index = waypointMarkers.indexOf(marker);
        if (index > -1) {
            map.removeLayer(marker);
            waypointMarkers.splice(index, 1);
            waypoints.splice(index, 1);
            updateRoute();
            updateMarkerIcons();
        }
    });

    // Return the newly created and configured DOM element for Leaflet to display
    return popupContent;
}

/**
 * Updates all waypoint marker icons on the map to reflect their current
 * status (start, end, intermediate, or hidden).
 */
function updateMarkerIcons() {
    const totalMarkers = waypointMarkers.length;

    waypointMarkers.forEach((marker, index) => {
        const waypoint = waypoints[index];

        // Update map marker icon
        const isStart = totalMarkers === 1 || index === 0;
        const isEnd = index === totalMarkers - 1 && totalMarkers > 1;
        if (waypoint.isHidden) {
            marker.setIcon(hiddenIcon);
        } else {
            // Set map icon based on position
            if (isStart) marker.setIcon(startIcon);
            else if (isEnd) marker.setIcon(endIcon);
            else marker.setIcon(waypointIcon);
        }
    });
}

/**
 * Fetches and draws the route on the map using the current waypoints.
 * It aborts any previously ongoing route requests.
 */
async function updateRoute() {
    if (newRouteLine) map.removeLayer(newRouteLine);

    if (waypoints.length < 2) return;

    // Abort any ongoing fetch requests
    if (routeRequestController) {
        routeRequestController.abort();
    }
    // Create a new AbortController for the new request
    routeRequestController = new AbortController();
    const signal = routeRequestController.signal;

    // Format coordinates and call the OSRM API
    const coordinates = waypoints.map(waypoint => `${waypoint.latlng.lng},${waypoint.latlng.lat}`).join(';');
    const url = `${OSRM_URL}/route/v1/driving/${coordinates}?overview=full&geometries=geojson`;

    try {
        const response = await fetch(url, { signal });
        if (!response.ok) throw new Error('Route not found');

        const data = await response.json();
        const routeGeometry = data.routes[0].geometry.coordinates;

        // OSRM returns [lng, lat], Leaflet needs [lat, lng]
        const latLngs = routeGeometry.map(coord => [coord[1], coord[0]]);

        // Create a new polyline and add it to the map
        newRouteLine = L.polyline(latLngs, { color: accentBlueHoverLight }).addTo(map);
    } catch (error) {
        // If the error is an AbortError, do nothing
        if (error.name === 'AbortError') {
            return;
        } else {
            console.error("Error fetching route:", error);
            flash("Error drawing route", 5000, { backgroundColor: accentOrange });
        }
    }
}

/**
 * Resets the Twist creation state, removing all waypoints, markers,
 * and the route line from the map and resetting UI elements.
 */
function stopTwistCreation() {
    // Immediate return if not creating Twist
    if (!mapContainer.classList.contains('creating-twist')) return;

    mapContainer.classList.remove('creating-twist');

    waypointMarkers.forEach(marker => map.removeLayer(marker));
    waypoints = [];
    waypointMarkers = [];

    if (newRouteLine) {
        map.removeLayer(newRouteLine);
        newRouteLine = null;
    }

    // Reset the status indicator and submit button
    const submitButton = twistForm.querySelector('[type="submit"]');
    const statusIndicator = document.querySelector('#route-status-indicator');
    submitButton.disabled = true;
    statusIndicator.classList.add('gone');
    writeToStatus(statusIndicator, "");

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
    const statusIndicator = document.querySelector('#route-status-indicator');

    // Check if there's a route to save
    const waypointsToSend = waypoints.filter(wp => !wp.isHidden);
    if (waypointsToSend.length > 1 && newRouteLine) {
        const routeLatLngs = newRouteLine.getLatLngs();

        // Enable submission of form
        const submitButton = twistForm.querySelector('[type="submit"]');
        submitButton.disabled = false;

        // Write success status
        writeToStatus(
            statusIndicator,
            `✅ Route captured with ${waypointsToSend.length} waypoints and ${routeLatLngs.length} geometry points.`
        );

        // Warn about unnamed waypoints on a new line
        const unnamedCount = waypointsToSend.filter(wp => !wp.name).length;
        if (unnamedCount > 0) {
            const noun = unnamedCount === 1 ? "waypoint" : "waypoints";
            const verb = unnamedCount === 1 ? "remains" : "remain";
            const message = `⚠️ ${unnamedCount} ${noun} ${verb} unnamed.`;

            writeToStatus(statusIndicator, message, "a");
        }
        statusIndicator.classList.remove('gone');

    } else {
        // Handle case where user finalizes without a valid route
        writeToStatus(
            statusIndicator,
            '⚠️ No valid route was created.'
        );
        statusIndicator.classList.remove('gone');
    }
});

// Handle cancellation of route geometry recording
cancelTwistButton.addEventListener('click', () => {
    stopTwistCreation();
});

// Listen for map clicks when recording route geometry
map.on('click', function(e) {
    if (!mapContainer.classList.contains('creating-twist')) return;

    // Create a new waypoint
    const newWaypoint = {
        latlng: e.latlng,
        name: '',
        isHidden: false
    };
    waypoints.push(newWaypoint);

    // Create a new marker
    const marker = L.marker(e.latlng, { draggable: true }).addTo(map);
    waypointMarkers.push(marker);

    // Bind a function that creates and returns the popup content on demand
    marker.bindPopup(() => createPopupContent(marker));

    // Listen for the marker being dragged and update route on end
    marker.on('dragend', (event) => {
        const index = waypointMarkers.indexOf(marker);
        if (index > -1) {
            // Redraw the route with the new coordinates
            waypoints[index].latlng = event.target.getLatLng();
            updateRoute();
        }
    });

    // Update the route line with the new waypoint
    updateRoute();
    updateMarkerIcons();
});

(function() {
    // Save the original send method so we can call it later
    const originalSend = XMLHttpRequest.prototype.send;

    // Override XHR send to intercept outgoing requests
    XMLHttpRequest.prototype.send = function(body) {
        // Check if this is a POST request to /twists
        if (this._url && this._url.endsWith('/twists') && this._method === 'POST') {
            // Serialize JSON
            bodyJSON = JSON.parse(body);

            // Build payload
            const waypointsToSend = waypoints.filter(wp => !wp.isHidden);
            bodyJSON.waypoints = waypointsToSend.map(wp => ({
                lat: wp.latlng.lat,
                lng: wp.latlng.lng,
                name: wp.name
            }));
            bodyJSON.route_geometry = newRouteLine.getLatLngs().map(coord => ({ lat: coord.lat, lng: coord.lng }));

            // Stringify JSON
            body = JSON.stringify(bodyJSON);
        }
        // Call the original send function to actually send the request
        return originalSend.apply(this, arguments);
    };

    // Save the original open method
    const originalOpen = XMLHttpRequest.prototype.open;

    // Override XHR open to capture the method and URL (for send)
    XMLHttpRequest.prototype.open = function(method, url) {
        this._method = method;
        this._url = url;
        return originalOpen.apply(this, arguments);
    };
})();