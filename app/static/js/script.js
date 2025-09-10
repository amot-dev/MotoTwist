// Initialize the map and set its view
const map = L.map('map').setView([49.2827, -123.1207], 9);

// Add a tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

// Object to store the map layers
const mapLayers = {};

/**
 * Loads a GPX track and adds it to the map with appropriate styling.
 * This is called only when a layer is first made visible.
 * @param {string} twistId - The ID of the twist to load.
 * @param {boolean} isPaved - Whether the road surface is paved.
 */
async function loadGpxLayer(twistId, twistName, isPaved) {
    // If layer already exists, don't re-load it
    if (mapLayers[twistId]) {
        return;
    }
    const gpxUrl = `/twists/${twistId}/gpx`;

    // Get the computed styles from the root element (the <html> tag)
    const rootStyles = getComputedStyle(document.documentElement);
    const pavedColor = rootStyles.getPropertyValue('--accent-blue').trim();
    const unpavedColor = rootStyles.getPropertyValue('--accent-orange').trim();
    const lineColor = isPaved ? pavedColor : unpavedColor;

    // Configure layer
    const gpxLayer = new L.GPX(gpxUrl, {
        async: true,
        markers: {
            startIcon: '/static/images/marker-icon-green.png',
            endIcon: '/static/images/marker-icon-red.png',
            wptIcons: {
                '': '/static/images/marker-icon-blue.png'
            }
        },
        marker_options: {
            iconSize: [19, 31], iconAnchor: [10, 31], shadowSize: [31, 31]
        },
        polyline_options: {
            color: lineColor, weight: 5, opacity: 0.85
        }
    });

    // Catch network errors (404, 500, etc)
    gpxLayer.on('error', function(e) {
        console.error(`Failed to load GPX file from ${gpxUrl}:`, e.error);
        delete mapLayers[twistId];
    });

    // Catches errors when the GPX file is invalid or cannot be parsed
    gpxLayer.on('gpx_failed', function(e) {
        console.error(`Failed to parse GPX file from ${gpxUrl}:`, e.err);
        delete mapLayers[twistId];
    });

    // Put start and end points above waypoints
    gpxLayer.on('addpoint', function(e) {
        if (e.point_type === 'start' || e.point_type === 'end') {
            e.point.setZIndexOffset(1000);

            // Very hacky way to keep popup from waypoint
            e.point.on('click', function(clickEvent) {
                const clickedMarker = clickEvent.target;
                const clickedLatLng = clickedMarker.getLatLng();

                // Find the first overlapping waypoint underneath the clicked marker
                const waypoint = gpxLayer.getLayers()[0].getLayers().find(layer => {
                    // Is it a waypoint?
                    if (!layer.options || !layer.options.icon || layer.options.title === undefined || layer === clickedMarker) {
                        return false;
                    }
                    return layer.getLatLng().distanceTo(clickedLatLng) < 1; // Is the waypoint within 1 meter?
                });

                if (waypoint && waypoint.getPopup()) {
                    // Get the waypoint's original, default popup content
                    const waypointContent = waypoint.getPopup().getContent();
                    // Open a new popup that is a clone of the waypoint's popup
                    L.popup()
                        .setLatLng(clickedLatLng)
                        .setContent(waypointContent)
                        .openOn(map);
                }
            });
        }
    });

    // Create popup for tracks
    gpxLayer.on('addline', function(e) {
        // Find the <name> and <desc> elements within the track's XML element
        const nameEl = e.element.querySelector('name');
        const descEl = e.element.querySelector('desc');

        // Get the text content, checking if the elements exist first
        const name = nameEl ? nameEl.textContent : '';
        const desc = descEl ? descEl.textContent : '';

        let popupContent = '';
        if (name && name != twistName) {
            popupContent += `<b>${twistName} (${name})</b>`;
        } else {
            popupContent += `<b>${twistName}</b>`;
        }
        if (desc) {
            // Using a <pre> tag preserves the line breaks from the description
            popupContent += `<pre>${desc.trim()}</pre>`;
        }

        // Bind the popup if we have content
        if (popupContent) {
            e.line.bindPopup(popupContent);
        }
    });
    
    // Store layer
    mapLayers[twistId] = gpxLayer;
    
    // Wait for it to load to add to map, allows fitting bounds before showing
    gpxLayer.on('loaded', () => {
        const listItem = document.querySelector(`.twist-item[data-twist-id='${twistId}']`);
        if (listItem && listItem.classList.contains('is-visible')) {
            gpxLayer.addTo(map);
        }
    });
}

/**
 * The master function to set the visibility state of a GPX layer and update its UI.
 * This removes duplicated logic from the toggle and restore functions.
 * @param {string} twistId - The ID of the twist to modify.
 * @param {boolean} makeVisible - True to show the layer, false to hide it.
 */
function setLayerVisibility(twistId, makeVisible) {
    const listItem = document.querySelector(`.twist-item[data-twist-id='${twistId}']`);
    if (!listItem) return;

    const icon = listItem.querySelector('.visibility-toggle i');

    // Use the second argument of classList.toggle() to set the state explicitly
    listItem.classList.toggle('is-visible', makeVisible);
    icon.classList.toggle('fa-eye', makeVisible);
    icon.classList.toggle('fa-eye-slash', !makeVisible);

    const layer = mapLayers[twistId];

    if (makeVisible) {
        if (layer) {
            // Layer is already loaded, just add it back to the map
            layer.addTo(map);
        } else {
            // First time showing this layer, load the GPX data
            const isPaved = listItem.dataset.paved === 'True';
            const twistName = listItem.querySelector('.twist-name').textContent;
            loadGpxLayer(twistId, twistName, isPaved);
        }
    } else {
        // Hide the layer
        if (layer && map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
    }

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
        if (!isCurrentlyOpen) ratingDropdown.classList.add('is-open');

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


// Listen for the flashMessage event from the server
document.body.addEventListener('flashMessage', (event) => {
    const message = event.detail.value;

    // Display the message for 3 seconds if it exists
    if (message) {
        const flashMessage = document.querySelector('.flash-message');
        if (flashMessage) {
            flashMessage.style.opacity = '1';
            flashMessage.innerHTML = message;
            setTimeout(() => {
                flashMessage.style.opacity = '0';
            }, 3000);
        }
    }
});