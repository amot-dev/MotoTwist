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

const shapingPointIcon = new L.Icon({
    iconUrl: '/static/images/marker-icon-grey.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize: [19, 31], iconAnchor: [10, 31], shadowSize: [31, 31]
});

/**
 * Loads a Twist's geometry data and adds it to the map as a new layer.
 * @param {string} twistId - The ID of the Twist to load.
 */
async function loadTwistLayer(twistId) {
    // If layer already exists, don't re-load it
    if (mapLayers[twistId]) return;

    // Fetch Twist data
    try {
        const response = await fetch(`/twists/${twistId}/geometry`);
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        const twist_data = await response.json();

        // Create the route line
        const lineColor = twist_data.is_paved ? accentBlue : accentOrange;
        const routeLine = L.polyline(twist_data.route_geometry, {
            color: lineColor,
            weight: 5,
            opacity: 0.85
        });
        routeLine.bindPopup(`<b>${twist_data.name}</b>`);

        // Create the waypoint markers
        const namedWaypoints = twist_data.waypoints.filter(wp => wp.name.length > 0);
        const waypointMarkers = namedWaypoints.map((point, index) => {
            let icon = waypointIcon;
            const totalPoints = namedWaypoints.length;

            if (totalPoints === 1 || index === 0) icon = startIcon;
            else if (index === totalPoints - 1) icon = endIcon;

            return L.marker(point, { icon: icon })
                .bindPopup(`<b>${twist_data.name}</b>${point.name ? `<br>${point.name}` : ''}`);
        });

        // Group all layers together
        const twistLayer = L.featureGroup([routeLine, ...waypointMarkers]);

        // Store and add the complete layer to the map
        mapLayers[twistId] = twistLayer;
        twistLayer.addTo(map);

    } catch (error) {
        console.error(`Failed to load route for Twist '${twistId}':`, error);
        flash(`Failed to load route for Twist '${twistId}'`)

        // Ensure a failed layer doesn't stick around
        delete mapLayers[twistId];
    }
}

/**
 * Set the visibility state of a Twist layer and update its UI.
 * @param {string} twistId - The ID of the Twist to modify.
 * @param {boolean} makeVisible - True to show the layer, false to hide it.
 */
function setLayerVisibility(twistId, makeVisible) {
    const layer = mapLayers[twistId];

    // Unload if hiding
    if (!makeVisible) {
        if (layer && map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
    }

    // Load layer if showing
    if (makeVisible) {
        if (layer) {
            // Layer is already loaded, just add it back to the map
            layer.addTo(map);
        } else {
            // First time showing this layer, load the Twist data
            loadTwistLayer(twistId);
        }
    }

    // Use the second argument of classList.toggle() to set the state explicitly
    const twistItem = document.querySelector(`.twist-item[data-twist-id='${twistId}']`);
    if (twistItem) {
        const icon = twistItem.querySelector('.visibility-toggle i');
        twistItem.classList.toggle('is-visible', makeVisible);
        icon.classList.toggle('fa-eye', makeVisible);
        icon.classList.toggle('fa-eye-slash', !makeVisible);
    }
}

/**
 * Iterates over Twists in the list and sets their visibility
 * based on what's saved in localStorage.
 */
function applyVisibilityFromStorage() {
    const visibleIdSet = getVisibleIdSet();

    const allTwistItems = document.querySelectorAll('.twist-item');
    allTwistItems.forEach(item => {
        const twistId = item.dataset.twistId;
        const shouldBeVisible = visibleIdSet.has(twistId);
        setLayerVisibility(twistId, shouldBeVisible);
    });
}

/**
 * Gets the current set of visible Twist IDs from localStorage.
 * @returns {Set<string>} A Set of visible Twist IDs.
 */
function getVisibleIdSet() {
    const visibleIdsFromStorage = JSON.parse(localStorage.getItem('visibleTwists')) || [];
    return new Set(visibleIdsFromStorage);
}

/**
 * Saves a Set of Twist IDs back to localStorage.
 * @param {Set<string>} idSet - The Set of visible Twist IDs to save.
 */
function saveVisibleIdSet(idSet) {
    localStorage.setItem('visibleTwists', JSON.stringify(Array.from(idSet)));
}

/**
 * Toggles the visibility of a single Twist ID in localStorage.
 * This is the main function for user clicks.
 * @param {string} twistId - The ID of the Twist to toggle.
 */
function toggleVisibilityInStorage(twistId) {
    const visibleIdSet = getVisibleIdSet();

    if (visibleIdSet.has(twistId)) {
        visibleIdSet.delete(twistId);
    } else {
        visibleIdSet.add(twistId);
    }

    saveVisibleIdSet(visibleIdSet);
}

/**
 * Ensures a Twist is marked as visible in localStorage.
 * Used when a new Twist is created.
 * @param {string} twistId - The ID of the Twist to make visible.
 */
function addVisibilityToStorage(twistId) {
    const visibleIdSet = getVisibleIdSet();
    visibleIdSet.add(twistId);
    saveVisibleIdSet(visibleIdSet);
}


/**
 * Removes a Twist's visibility from localStorage.
 * Used when a Twist is deleted.
 * @param {string} twistId - The ID of the Twist to remove.
 */
function removeVisibilityFromStorage(twistId) {
    const visibleIdSet = getVisibleIdSet();
    visibleIdSet.delete(twistId);
    saveVisibleIdSet(visibleIdSet);
}

// Listen for the custom event sent from the server after the Twist list is initially loaded
document.body.addEventListener('twistsLoaded', () => {
    applyVisibilityFromStorage();
});

// Listen for the custom event sent from the server after a new Twist is created
document.body.addEventListener('twistAdded', (event) => {
    const newTwistId = event.detail.value;
    if (newTwistId) {
        addVisibilityToStorage(newTwistId);
        setLayerVisibility(newTwistId, true);
    }
});

// Listen for the custom event sent from the server after a Twist is deleted
document.body.addEventListener('twistDeleted', (event) => {
    const deletedTwistId = event.detail.value;
    if (deletedTwistId) {
        removeVisibilityFromStorage(deletedTwistId);
        setLayerVisibility(deletedTwistId, false);
    }
});

// Listen for clicks on Twists
document.getElementById('twist-list').addEventListener('click', function(event) {
    const twistItem = event.target.closest('.twist-item');
    if (!twistItem) return;

    const twistId = twistItem.dataset.twistId;

    if (event.target.closest('.visibility-toggle')) {
        // Clicked on the eye icon
        toggleVisibilityInStorage(twistId);
        setLayerVisibility(twistId, getVisibleIdSet().has(twistId));
    } else if (event.target.closest('.twist-header')) {
        // Clicked on the Twist name
        const twistDropdown = twistItem.querySelector('.twist-dropdown');
        const isCurrentlyOpen = twistDropdown.classList.contains('is-open');

        // Hide all Twist dropdowns
        const alltwistDropdowns = twistItem.closest('#twist-list').querySelectorAll('.twist-dropdown');
        alltwistDropdowns.forEach(container => {
            container.classList.remove('is-open');
        });

        // Show current Twist dropdown if it was hidden
        if (!isCurrentlyOpen) {
            twistDropdown.classList.add('is-open');

            // Load content if needed
            if (twistDropdown.querySelector('.loading')) {
                const twistHeader = twistItem.querySelector('.twist-header')
                htmx.trigger(twistHeader, 'load-twist-dropdown');
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

/* Includes visibleIds in query params */
document.body.addEventListener('htmx:configRequest', function(event) {
    // Check if this is a request to our list endpoint
    if (event.detail.path === '/twists/templates/list') {
        // Skip adding if no visibleIds
        const visibleIds = Array.from(getVisibleIdSet());
        if (visibleIds.length === 0) return;

        // No need to add visibleIds if not used
        if (event.detail.parameters['visibility'] === 'all') return;

        event.detail.parameters['visible_ids'] = visibleIds;
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
 * Configures whether or not a shaping point can be edited, based off the user action and the existing text.
 * @param {object} waypoint The waypoint object.
 * @param {HTMLElement} editIcon The <i> element for the icon.
 */
function configureShapingPointPopup(fromClick, editIcon, nameInput) {
    // If text exists or we've just clicked on the edit button, enable editing
    if (fromClick || nameInput.value.length > 0) {
        // Re-enable the input
        nameInput.disabled = false;
        nameInputTemplate = document.querySelector('#create-waypoint-popup-template').content.querySelector('input')
        nameInput.placeholder = nameInputTemplate.placeholder;
    } else {
        // Disable the input and set its text
        nameInput.disabled = true;
        nameInput.placeholder = 'Shaping Point';
        nameInput.title = 'Shaping Points are stored for routing but not displayed'
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
    const editButton = popupContent.querySelector('.popup-button-edit');
    const editIcon = editButton.querySelector('i');
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

    // Toggle visibility of the edit button for start/end markers
    const isStart = index === 0;
    const isEnd = index === totalMarkers - 1 && totalMarkers > 1;
    editButton.classList.toggle('gone', isStart || isEnd);

    // Set midpoints as shaping points
    if (!(isStart || isEnd)) {
        configureShapingPointPopup(false, editIcon, nameInput)
    }

    // Edit button
    editButton.addEventListener('click', () => {
        configureShapingPointPopup(true, editIcon, nameInput)
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
 * Updates a single waypoint marker icon on the map to reflect its
 * current status.
 *
 * @param {L.Marker} marker The marker to update.
 * @param {object} waypoint The corresponding waypoint data object.
 * @param {number} index The index of the marker in the array.
 * @param {number} totalMarkers The total number of markers.
 */
function updateMarkerIcon(marker, waypoint, index, totalMarkers) {
    const isStart = totalMarkers === 1 || index === 0;
    const isEnd = index === totalMarkers - 1 && totalMarkers > 1;

    // Set map icon based on position and presence of name
    if (isStart) marker.setIcon(startIcon);
    else if (isEnd) marker.setIcon(endIcon);
    else if (waypoint.name.length === 0) marker.setIcon(shapingPointIcon);
    else marker.setIcon(waypointIcon);
}

/**
 * Updates all waypoint marker icons on the map to reflect their current
 * status (start, end, shaping, named waypoint).
 */
function updateMarkerIcons() {
    const totalMarkers = waypointMarkers.length;

    waypointMarkers.forEach((marker, index) => {
        const waypoint = waypoints[index];
        updateMarkerIcon(marker, waypoint, index, totalMarkers);
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
if (createTwistButton) {
    createTwistButton.addEventListener('click', () => {
        mapContainer.classList.add('creating-twist');
        flash('Click on the map to create a Twist!', 5000);

        // Swap button visibility
        createTwistButton.classList.add('gone');
        finalizeTwistButton.classList.remove('gone');
        cancelTwistButton.classList.remove('gone');
    });
}

// Handle saving of route geometry
if (finalizeTwistButton) {
    finalizeTwistButton.addEventListener('click', () => {
        const statusIndicator = document.querySelector('#route-status-indicator');

        // Check if there's a route to save
        const namedWaypoints = waypoints.filter(wp => wp.name.length > 0);
        const shapingPoints = waypoints.filter(wp => wp.name.length === 0);
        if (waypoints.length > 1 && newRouteLine) {
            if (waypoints.at(0).name.length > 0 && waypoints.at(-1).name.length > 0) {
                const routeLatLngs = newRouteLine.getLatLngs();

                // Enable submission of form
                const submitButton = twistForm.querySelector('[type="submit"]');
                submitButton.disabled = false;

                // Write success status
                writeToStatus(
                    statusIndicator,
                    `✅ Route captured with ${namedWaypoints.length} waypoints and ${routeLatLngs.length} geometry points.`
                );

                // Inform about shaping points on a new line
                if (shapingPoints.length > 0) {
                    const noun = shapingPoints.length === 1 ? "shaping point" : "shaping points";
                    const message = `ℹ️ ${shapingPoints.length} ${noun} will be stored for routing but not displayed.`;

                    writeToStatus(statusIndicator, message, "a");
                }
            } else {
                // Handle case where user finalizes without naming start or end
                writeToStatus(
                    statusIndicator,
                    '⚠️ Start/End waypoint(s) remain unnamed.'
                );
            }
        } else {
            // Handle case where user finalizes without a valid route
            writeToStatus(
                statusIndicator,
                '⚠️ No valid route was created.'
            );
        }
        statusIndicator.classList.remove('gone');
    });
}

// Handle cancellation of route geometry recording
if (cancelTwistButton) {
    cancelTwistButton.addEventListener('click', () => {
        stopTwistCreation();
    });
}

// Listen for map clicks when recording route geometry
map.on('click', function(e) {
    if (!mapContainer.classList.contains('creating-twist')) return;

    // Create a new waypoint
    const newWaypoint = {
        latlng: e.latlng,
        name: '',
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

    // Listen for the marker's popup being closed and update icons
    marker.getPopup().on('remove', function() {
        updateMarkerIcons();
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
            bodyJSON.waypoints = waypoints.map(wp => ({
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