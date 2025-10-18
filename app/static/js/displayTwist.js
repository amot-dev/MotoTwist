import { stopTwistCreation } from './createTwist.js';
import { flash } from './flash.js';
import {
    startIcon,
    endIcon,
    waypointIcon
} from './map.js';
import { getRootProperty } from './utils.js';


// Object to store the map layers
/** @type {Object<string, L.FeatureGroup>} */
const mapLayers = {};

const accentBlue = getRootProperty('--accent-blue');
const accentOrange = getRootProperty('--accent-orange');


/**
 * Gets the current set of visible Twist IDs from localStorage.
 * @returns {Set<string>} A Set of visible Twist IDs.
 */
function getVisibleIdSet() {
    const visibleIdsFromStorage = JSON.parse(localStorage.getItem('visibleTwists') || "[]");
    return new Set(visibleIdsFromStorage);
}


/**
 * Saves a Set of Twist IDs back to localStorage.
 *
 * @param {Set<string>} idSet The Set of visible Twist IDs to save.
 */
function saveVisibleIdSet(idSet) {
    localStorage.setItem('visibleTwists', JSON.stringify(Array.from(idSet)));
}


/**
 * Toggles the visibility of a single Twist ID in localStorage.
 * This is the main function for user clicks.
 *
 * @param {string} twistId The ID of the Twist to toggle.
 * @return The new visibility of the Twist.
 */
function toggleVisibilityInStorage(twistId) {
    const visibleIdSet = getVisibleIdSet();

    let visible = false;
    if (visibleIdSet.has(twistId)) {
        visibleIdSet.delete(twistId);
    } else {
        visibleIdSet.add(twistId);
        visible = true;
    }

    saveVisibleIdSet(visibleIdSet);
    return visible;
}


/**
 * Ensures a Twist is marked as visible in localStorage.
 * Used when a new Twist is created.
 *
 * @param {string} twistId The ID of the Twist to make visible.
 */
function addVisibilityToStorage(twistId) {
    const visibleIdSet = getVisibleIdSet();
    visibleIdSet.add(twistId);
    saveVisibleIdSet(visibleIdSet);
}


/**
 * Removes a Twist's visibility from localStorage.
 * Used when a Twist is deleted.
 *
 * @param {string} twistId The ID of the Twist to remove.
 */
function removeVisibilityFromStorage(twistId) {
    const visibleIdSet = getVisibleIdSet();
    visibleIdSet.delete(twistId);
    saveVisibleIdSet(visibleIdSet);
}


/**
 * Loads a Twist's geometry data and adds it to the map as a new layer.
 *
 * @param {L.Map} map The map to load a Twist onto.
 * @param {string} twistId The ID of the Twist to load.
 */
async function loadTwistLayer(map, twistId) {
    // If layer already exists, don't re-load it
    if (mapLayers[twistId]) return;

    // Fetch Twist data
    try {
        const response = await fetch(`/twists/${twistId}/geometry`);
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }

        /** @type {TwistGeometryData} */
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
        flash(`Failed to load route for Twist '${twistId}'`, 5000, accentOrange)

        // Ensure a failed layer doesn't stick around
        delete mapLayers[twistId];
    }
}


/**
 * Set the visibility state of a Twist layer and update its UI.
 *
 * @param {L.Map} map The map to set the visibility of a Twist on.
 * @param {string} twistId The ID of the Twist to modify.
 * @param {boolean} makeVisible True to show the layer, false to hide it.
 */
function setLayerVisibility(map, twistId, makeVisible) {
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
            loadTwistLayer(map, twistId);
        }
    }

    // Use the second argument of classList.toggle() to set the state explicitly
    const twistItem = document.querySelector(`.twist-item[data-twist-id='${twistId}']`);
    if (twistItem) {
        const icon = twistItem.querySelector('.visibility-toggle i'); if (!icon) throw new Error("Critical element .visibility-toggle icon is missing!");
        twistItem.classList.toggle('is-visible', makeVisible);
        icon.classList.toggle('fa-eye', makeVisible);
        icon.classList.toggle('fa-eye-slash', !makeVisible);
    }
}


/**
 * Iterates over Twists in the list and sets their visibility
 * based on what's saved in localStorage.
 *
 * @param {L.Map} map The map to set the visibility of Twists on.
 */
function applyVisibilityFromStorage(map) {
    const visibleIdSet = getVisibleIdSet();

    /** @type {NodeListOf<HTMLElement>} */
    const allTwistItems = document.querySelectorAll('.twist-item');
    allTwistItems.forEach(item => {
        const twistId = item.dataset.twistId;
        if (!twistId) throw new Error("Critical element .twist-item is missing twistId data!");

        const shouldBeVisible = visibleIdSet.has(twistId);
        setLayerVisibility(map, twistId, shouldBeVisible);
    });
}


/**
 * Pans and zooms the map to fit the bounds of a specific Twist if it
 * is loaded. Does not check visibility.
 *
 * @param {L.Map} map - The map to pan and zoom to the Twist on.
 * @param {string} twistId - The ID of the Twist to show.
 */
function showTwistOnMap(map, twistId) {
    // Pan and zoom the map
    const layer = mapLayers[twistId];
    if (layer) {
        // If bounds are already available, use them. Otherwise, wait for the 'loaded' event
        if (layer.getBounds().isValid()) {
            map.fitBounds(layer.getBounds());
        } else {
            layer.on('loaded',
                /** @param {{ target: L.FeatureGroup }} event */
                (event) => map.fitBounds(event.target.getBounds())
            );
        }
    }
}


/**
 * Sets up all event listeners related to managing and interacting
 * with the list of Twists.
 *
 * This function uses event delegation on the body and '#twist-list'
 * to handle:
 * - Loading initial layer visibility ('twistsLoaded').
 * - Adding/removing layers on create/delete ('twistAdded', 'twistDeleted').
 * - Toggling layer visibility via the '.visibility-toggle' button.
 * - Expanding/collapsing Twist dropdowns and fitting map bounds on click.
 * - Modifying Twist list requests to include visible Twist IDs.
 *
 * @param {L.Map} map The main Leaflet map instance.
 * @returns {void}
 */
export function registerTwistListeners(map) {
    // Listen for the custom event sent from the server after the Twist list is initially loaded
    document.body.addEventListener('twistsLoaded', () => {
        applyVisibilityFromStorage(map);
    });

    // Listen for the custom event sent from the server after a new Twist is created
    document.body.addEventListener('twistAdded', (event) => {
        const customEvent = /** @type {CustomEvent<{value: string}>} */ (event);

        const newTwistId = customEvent.detail.value;
        if (newTwistId) {
            stopTwistCreation(map);
            addVisibilityToStorage(newTwistId);
            setLayerVisibility(map, newTwistId, true);
        }
    });

    // Listen for the custom event sent from the server after a Twist is deleted
    document.body.addEventListener('twistDeleted', (event) => {
        const customEvent = /** @type {CustomEvent<{value: string}>} */ (event);

        const deletedTwistId = customEvent.detail.value;
        if (deletedTwistId) {
            removeVisibilityFromStorage(deletedTwistId);
            setLayerVisibility(map, deletedTwistId, false);
        }
    });

    // Listen for clicks on Twists
    const twistList = document.getElementById('twist-list');
    if (twistList) {
        twistList.addEventListener('click', function(event) {
            if (!(event.target instanceof Element)) return;

            /** @type {HTMLElement | null} */
            const twistItem = event.target.closest('.twist-item');
            if (!twistItem) return;

            const twistId = twistItem.dataset.twistId;
            if (!twistId) throw new Error("Critical element .twist-item is missing twistId data!");

            if (event.target.closest('.visibility-toggle')) {
                // Clicked on the eye icon
                let visibility = toggleVisibilityInStorage(twistId);
                setLayerVisibility(map, twistId, visibility);

                // If the Twist just became visible, show it
                if (visibility) showTwistOnMap(map, twistId)

            } else if (event.target.closest('.twist-header')) {
                // Clicked on the Twist name
                const twistDropdown = twistItem.querySelector('.twist-dropdown');
                if (!(twistDropdown instanceof HTMLElement)) throw new Error("Critical element .twist-dropdown is missing!");
                const isCurrentlyOpen = twistDropdown.classList.contains('is-open');

                // Hide all Twist dropdowns
                const twistList = twistItem.closest('#twist-list'); if (!twistList) throw new Error("Critical element .twist-list is missing!");
                const alltwistDropdowns = twistList.querySelectorAll('.twist-dropdown');
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

                // Show the Twist on the map after opening its dropdown
                showTwistOnMap(map, twistId)
            }
        });
    }

    // Include visibleIds in query params for Twist list requests
    document.body.addEventListener('htmx:configRequest', function(event) {
        const customEvent = /** @type {CustomEvent<{path: string, parameters: Record<string, any>}>} */ (event);

        // Check if this is a request to our list endpoint
        if (customEvent.detail.path === '/twists/templates/list') {
            // Skip adding if no visibleIds
            const visibleIds = Array.from(getVisibleIdSet());
            if (visibleIds.length === 0) return;

            // No need to add visibleIds if not used
            if (customEvent.detail.parameters['visibility'] === 'all') return;

            customEvent.detail.parameters['visible_ids'] = visibleIds;
        }
    });
}