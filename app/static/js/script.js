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
    updateVisibleTwistsInStorage();
}

/**
 * Saves the list of currently visible twist IDs to localStorage.
 * (This function remains unchanged as it serves a distinct purpose).
 */
function updateVisibleTwistsInStorage() {
    const visibleItems = document.querySelectorAll('.twist-item.is-visible');
    const visibleIds = Array.from(visibleItems).map(item => item.dataset.twistId);
    localStorage.setItem('visibleTwists', JSON.stringify(visibleIds));
}

/**
 * On page load, reads localStorage and sets the visibility for ALL layers.
 * Explicitly hides layers that are not in the saved list.
 */
function restoreVisibleLayers() {
    const visibleIdsFromStorage = JSON.parse(localStorage.getItem('visibleTwists')) || [];
    // Using a Set provides a fast O(1) lookup
    const visibleIdSet = new Set(visibleIdsFromStorage);

    const newTwistId = document.body.dataset.newTwist;
    if (newTwistId && !visibleIdSet.has(newTwistId)) {
        // If there's a new ID, ensure it gets added to the visible set and saved
        visibleIdSet.add(newTwistId);
        localStorage.setItem('visibleTwists', JSON.stringify(Array.from(visibleIdSet)));
    }
    
    // Iterate over ALL twist items to explicitly set their initial state.
    const allTwistItems = document.querySelectorAll('.twist-item');
    allTwistItems.forEach(item => {
        const twistId = item.dataset.twistId;
        const shouldBeVisible = visibleIdSet.has(twistId);
        setLayerVisibility(twistId, shouldBeVisible);
    });
}

/**
 * Fetches and displays ratings for a twist.
 * @param {string} twistId - The ID of the twist.
 * @param {HTMLElement} ratingsContainer - The div to populate.
 */
async function loadRatings(twistId, ratingsContainer) {
    if (ratingsContainer.dataset.loaded) return;
    ratingsContainer.dataset.loaded = 'true';

    try {
        const response = await fetch(`/twists/${twistId}/averages`);
        if (!response.ok) throw new Error('Network response was not ok.');
        
        const avgRatings = await response.json();

        // Display both paved and unpaved ratings dynamically
        const avgRatingsHTML = Object.entries(avgRatings).map(([key, value]) => {
            // Capitalize the first letter of the key for display
            const formattedKey = key.charAt(0).toUpperCase() + key.slice(1);
            return `<li>${formattedKey}: ${value}/10</li>`;
        }).join('');

        // Add ratings to list
        const ul = ratingsContainer.querySelector('ul');
        const allRatingsLink = ratingsContainer.querySelector('a')
        if (avgRatingsHTML) {
            ul.innerHTML = avgRatingsHTML;
            allRatingsLink.style.display = null;
        }
        else {
            ul.innerHTML = "No ratings yet!"
            allRatingsLink.style.display = 'none';
        }

    } catch (error) {
        ul.innerHTML = '<li>Could not load ratings.</li>';
        console.error('Failed to fetch ratings:', error);
    }
}

// Fade out flash message
document.addEventListener('DOMContentLoaded', () => {
  const flashMessage = document.querySelector('.flash-message');

    if (flashMessage) {
        setTimeout(() => {
            flashMessage.style.opacity = '0';
            flashMessage.addEventListener('transitionend', () => {
                flashMessage.remove();
            }, { once: true });
        }, 3000);
    }
});

// Restore visible map layers on page load
document.addEventListener('DOMContentLoaded', restoreVisibleLayers);

// Listen for clicks on twists
document.getElementById('twist-list').addEventListener('click', function(event) {
    const twistItem = event.target.closest('.twist-item');
    if (!twistItem) return;

    const twistId = twistItem.dataset.twistId;
    const isPaved = twistItem.dataset.paved === 'True';

    
    if (event.target.closest('.visibility-toggle')) {
        // Clicked on the eye icon
        setLayerVisibility(twistId, !twistItem.classList.contains('is-visible'));
    } else if (event.target.closest('.twist-header')) {
        // Clicked on the twist name
        const ratingsContainer = twistItem.querySelector('.ratings-container');
        const isCurrentlyOpen = ratingsContainer.classList.contains('is-open');

        // Hide all ratings containers
        const allContainers = twistItem.closest('#twist-list').querySelectorAll('.ratings-container');
        allContainers.forEach(container => {
            container.classList.remove('is-open');
        });

        // Show current rating container if it was hidden
        if (!isCurrentlyOpen) {
            ratingsContainer.classList.add('is-open');
            loadRatings(twistId, ratingsContainer);
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

// Modal opening/closing
document.addEventListener('DOMContentLoaded', () => {
    const openModalTriggers = document.querySelectorAll('[data-modal-target]');
    openModalTriggers.forEach(button => {
        button.addEventListener('click', () => {
            const modalId = button.dataset.modalTarget;
            if (!modalId) return;

            const modal = document.querySelector(modalId);
            if (modal) {
                // Get the twistId if it exists
                const twistId = button.dataset.twistId;
                openModal(modal, twistId);
            }
        });
    });

    async function setupRateTwistModal(form, twistId) {
        const actionTemplate = form.dataset.actionTemplate;
        form.action = actionTemplate.replace('{id}', twistId);

        const title = form.previousElementSibling;
        const pavedContainer = form.querySelector('#paved-criteria');
        const unpavedContainer = form.querySelector('#unpaved-criteria');

        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) submitButton.disabled = true;

        title.textContent = 'Loading ratings...';
        try {
            const response = await fetch(`/twists/${twistId}`);
            if (!response.ok) throw new Error('Network response was not ok.');

            const twist = await response.json();

            // Get all input elements within each container
            const pavedInputs = pavedContainer.querySelectorAll('input');
            const unpavedInputs = unpavedContainer.querySelectorAll('input');

            title.textContent = twist.name;

            if (twist.is_paved) {
                pavedContainer.style.display = 'block';
                unpavedContainer.style.display = 'none';

                // Enable the visible inputs and disable the hidden ones
                pavedInputs.forEach(input => input.disabled = false);
                unpavedInputs.forEach(input => input.disabled = true);
            } else {
                pavedContainer.style.display = 'none';
                unpavedContainer.style.display = 'block';

                // Enable the visible inputs and disable the hidden ones
                pavedInputs.forEach(input => input.disabled = true);
                unpavedInputs.forEach(input => input.disabled = false);
            }

            if (submitButton) submitButton.disabled = false;

        } catch (error) {
            title.textContent = 'Error loading twist details';
            console.error('Failed to fetch twist details:', error);
        }
    };

    async function setupTwistRatingsModal(modal, twistId) {
        const ratingsListContainer = modal.querySelector('#ratings-list-container');
        const title = modal.querySelector('h1');

        title.textContent = 'Loading ratings...';
        try {
            const twistResponse = await fetch(`/twists/${twistId}`);
            if (!twistResponse.ok) throw new Error('Network response was not ok.');

            const twistRatingResponse = await fetch(`/twists/${twistId}/ratings`);
            if (!twistRatingResponse.ok) throw new Error('Network response was not ok.');

            const twist = await twistResponse.json()
            const ratings = await twistRatingResponse.json();

            title.textContent = twist.name;

            // Create and append a card for each rating entry
            ratings.forEach(ratingEntry => {
                const ratingCard = document.createElement('div');
                ratingCard.className = 'rating-card';

                const dateElement = document.createElement('h3');
                // Format date for better readability if desired
                const date = new Date(ratingEntry.rating_date + 'T00:00:00'); // Avoid timezone issues
                dateElement.textContent = `Date: ${date.toLocaleDateString()}`;
                ratingCard.appendChild(dateElement);

                const criteriaList = document.createElement('ul');
                
                // Iterate over the ratings object to display each criterion
                for (const [criteria, score] of Object.entries(ratingEntry.ratings)) {
                    const listItem = document.createElement('li');
                    // Capitalize the first letter of the criteria name
                    const capitalizedCriteria = criteria.charAt(0).toUpperCase() + criteria.slice(1);
                    listItem.textContent = `${capitalizedCriteria}: ${score}/10`;
                    criteriaList.appendChild(listItem);
                }

                ratingCard.appendChild(criteriaList);
                ratingsListContainer.appendChild(ratingCard);
                ratingsListContainer.dataset.paved = twist.is_paved;
            });

        } catch (error) {
            title.textContent = 'Error loading twist ratings';
            console.error('Failed to fetch twist ratings:', error);
        }
    };

    const openModal = (modal, twistId) => {
        if (twistId) {
            const form = modal.querySelector('form');
            if (form && form.dataset.actionTemplate) {
                setupRateTwistModal(form, twistId)
            } else {
                setupTwistRatingsModal(modal, twistId)
            }
        }
        modal.style.display = 'flex';
    };

    const closeModal = (modal) => {
        modal.style.display = 'none';
        const form = modal.querySelector('form');
        if (form) {
            form.reset();
        }
    };

    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        // Close when clicking the background overlay
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                closeModal(modal);
            }
        });

        // Find and attach listeners to all close/cancel buttons within this modal
        const closeButtons = modal.querySelectorAll('.close-button, .cancel-button');
        closeButtons.forEach(button => {
            button.addEventListener('click', () => {
                closeModal(modal);
            });
        });
    });
});