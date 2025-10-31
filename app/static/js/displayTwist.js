import { stopTwistCreation } from './createTwist.js';
import { flash } from './flash.js';
import {
    startIcon,
    endIcon,
    waypointIcon
} from './map.js';
import { doubleClickTimeout, getRootProperty } from './utils.js';


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
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds);
        } else {
            console.warn(`Cannot fit map to Twist '${twistId}' because its layer has no valid bounds.`);
        }
    }
}


/**
 * Loads a Twist's geometry data and adds it to the map as a new layer.
 *
 * @param {L.Map} map The map to load a Twist onto.
 * @param {string} twistId The ID of the Twist to load.
 * @param {boolean} [show=false] If true, pan/zoom to the Twist after load.
 */
async function loadTwistLayer(map, twistId, show = false) {
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
        if (show) showTwistOnMap(map, twistId);

    } catch (error) {
        console.error(`Failed to load route for Twist '${twistId}':`, error);
        flash(`Failed to load route for Twist '${twistId}'`, { duration: 5000, type: 'error' })

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
 * @param {boolean} [show=false] If true and `makeVisible` is true, show Twist on map.
 */
async function setTwistVisibility(map, twistId, makeVisible, show = false) {
    const layer = mapLayers[twistId];

    // Update eye icon
    const twistItem = document.querySelector(`.twist-item[data-twist-id='${twistId}']`);
    if (twistItem) {
        const icon = twistItem.querySelector('.visibility-toggle i');
        if (!icon) throw new Error("Critical element .visibility-toggle icon is missing!");

        twistItem.classList.toggle('is-visible', makeVisible);
        icon.classList.toggle('fa-eye', makeVisible);
        icon.classList.toggle('fa-eye-slash', !makeVisible);
    }

    // Unload if hiding
    if (!makeVisible) {
        if (layer && map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
        return;
    }

    // Load layer if showing
    if (layer) {
        // Layer is already loaded, just add it back to the map
        layer.addTo(map);
        if (show) showTwistOnMap(map, twistId);
    } else {
        // First time showing this layer, load the Twist data
        await loadTwistLayer(map, twistId, show);
    }
}


/**
 * Iterates over Twists in the list and sets their visibility
 * based on what's saved in localStorage.
 *
 * @param {L.Map} map The map to set the visibility of Twists on.
 */
function applyTwistVisibilityFromStorage(map) {
    const visibleIdSet = getVisibleIdSet();

    /** @type {NodeListOf<HTMLElement>} */
    const allTwistItems = document.querySelectorAll('.twist-item');
    allTwistItems.forEach(item => {
        const twistId = item.dataset.twistId;
        if (!twistId) throw new Error("Critical element .twist-item is missing twistId data!");

        const shouldBeVisible = visibleIdSet.has(twistId);
        setTwistVisibility(map, twistId, shouldBeVisible);
    });
}


/**
 * Gets the geographic coordinates (Lat/Lng) at the center of the viewport,
 * accounting for map offsets (such as the sidebar).
 *
 * @param {L.Map} map - The active Leaflet map instance.
 * @returns {L.LatLng} The coordinates at the visual center of the screen.
 */
function getVisualMapCenter(map) {
    // Get the pixel center of the entire window
    const visualCenterX = window.innerWidth / 2;
    const visualCenterY = window.innerHeight / 2;

    // Get the map div's position and size
    const mapRect = map.getContainer().getBoundingClientRect();

    // Calculate the center point relative to the map's div
    const relativeX = visualCenterX - mapRect.left;
    const relativeY = visualCenterY - mapRect.top;

    // Convert this relative pixel coordinate to a Lat/Lng and return it
    return map.containerPointToLatLng(L.point(relativeX, relativeY));
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
        applyTwistVisibilityFromStorage(map);
    });

    // Listen for the custom event sent from the server after a new Twist is created
    document.body.addEventListener('twistAdded', (event) => {
        const customEvent = /** @type {CustomEvent<{value: string}>} */ (event);

        const newTwistId = customEvent.detail.value;
        if (newTwistId) {
            stopTwistCreation(map);
            addVisibilityToStorage(newTwistId);
            setTwistVisibility(map, newTwistId, true, true);
        }
    });

    // Listen for the custom event sent from the server after a Twist is deleted
    document.body.addEventListener('twistDeleted', (event) => {
        const customEvent = /** @type {CustomEvent<{value: string}>} */ (event);

        const deletedTwistId = customEvent.detail.value;
        if (deletedTwistId) {
            removeVisibilityFromStorage(deletedTwistId);
            setTwistVisibility(map, deletedTwistId, false);
        }
    });

    const twistList = document.getElementById('twist-list');
    if (!twistList) throw new Error("Critical element #twist-list is missing!");

    /** @type {string | null} */
    let activeTwistId = null;

    // Listen for clicks on Twists
    let twistListClickCount = 0
    let twistListClickTimer = 0;
    twistList.addEventListener('click', function(event) {
        if (!(event.target instanceof Element)) return;

        /** @type {HTMLElement | null} */
        const twistItem = event.target.closest('.twist-item');
        if (!twistItem) return;

        const twistId = twistItem.dataset.twistId;
        if (!twistId) throw new Error("Critical element .twist-item is missing twistId data!");

        twistListClickCount++;
        if (twistListClickCount === 1) {
            twistListClickTimer = setTimeout(function() {
                twistListClickCount = 0;
                if (!(event.target instanceof Element)) return;

                // Toggle visibility or dropdown on single click
                if (event.target.closest('.visibility-toggle')) {
                    // Clicked on the eye icon
                    let visibility = toggleVisibilityInStorage(twistId);
                    setTwistVisibility(map, twistId, visibility);
                } else if (event.target.closest('.twist-header')) {
                    activeTwistId = null;

                    // Clicked on the Twist header
                    const twistDropdown = twistItem.querySelector('.twist-dropdown');
                    if (!(twistDropdown instanceof HTMLElement)) throw new Error("Critical element .twist-dropdown is missing!");
                    const isCurrentlyOpen = twistDropdown.classList.contains('is-open');

                    // Hide all Twist dropdowns
                    const alltwistDropdowns = twistList.querySelectorAll('.twist-dropdown');
                    alltwistDropdowns.forEach(container => {
                        container.classList.remove('is-open');
                    });

                    // Show current Twist dropdown if it was hidden
                    if (!isCurrentlyOpen) {
                        twistDropdown.classList.add('is-open');
                        activeTwistId = twistItem.dataset.twistId ?? null;

                        // Load content if needed
                        if (twistDropdown.querySelector('.loading')) {
                            const twistHeader = twistItem.querySelector('.twist-header')
                            htmx.trigger(twistHeader, 'loadDropdown');
                        }
                    }
                }
            }, doubleClickTimeout);
        } else if (twistListClickCount === 2) {
            clearTimeout(twistListClickTimer);
            twistListClickCount = 0;

            // Show the Twist on the map on double click
            showTwistOnMap(map, twistId)

            // Clear text selection
            const selection = document.getSelection();
            if(selection) selection.empty();
        }
    });

    // Order Twist list on map move ending (debounced on htmx listen side)
    map.on('moveend', function() {
        htmx.trigger(document.body, 'mapCenterChange')
    });

    // Include additional parameters for Twist list requests
    document.body.addEventListener('htmx:configRequest', function(event) {
        const customEvent = /** @type {CustomEvent<{path: string, parameters: Record<string, any>, triggeringEvent: Event | null}>} */ (event);

        // Check if this is a request to the Twist list endpoint
        if (customEvent.detail.path === '/twists/templates/list') {
            // Maintain current page on mapCenterChange and authChange
            const trigger = customEvent.detail.triggeringEvent;
            if (trigger) {
                if (['mapCenterChange', 'authChange'].includes(trigger.type)) {
                    const twistListPagination = document.getElementById('twist-list-pagination');
                    if (!twistListPagination) throw new Error("Critical element #twist-list-pagination is missing!");

                    // Set page to current or 1 if current doesn't exist
                    customEvent.detail.parameters['page'] = twistListPagination.dataset.currentPage ?? 1;
                }
            }

            if (activeTwistId) customEvent.detail.parameters['open_id'] = activeTwistId;

            // Only add visibleIds if they exist or they will be needed
            const visibleIds = Array.from(getVisibleIdSet());
            if (visibleIds.length > 0 && customEvent.detail.parameters['visibility'] != 'all') {
                customEvent.detail.parameters['visible_ids'] = visibleIds;
            }

            /** @type {L.LatLng} */
            const mapCenter = getVisualMapCenter(map);
            customEvent.detail.parameters['map_center_lat'] = mapCenter.lat;
            customEvent.detail.parameters['map_center_lng'] = mapCenter.lng;
        }
    });
}