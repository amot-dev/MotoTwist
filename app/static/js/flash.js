/** @type {HTMLUListElement | null} */
let flashContainer = document.querySelector('.flash-container');
if (!(flashContainer instanceof HTMLUListElement)) throw new Error("Critical element .flash-container is missing or not a <ul>!");


/**
 * Displays a flash message by creating and appending a new element.
 *
 * @param {string} message The message string to display. Can include HTML.
 * @param {object} [options] Configuration options.
 * @param {number} [options.duration=3000] How long to display in ms. 0 = persistent.
 * @param {'info'|'error'|'loading'} [options.type='info'] Message type for styling.
 * @returns {(() => void) | null} A remove function if persistent, else null.
 */
export function flash(message, options = {}) {
    if (!message) return null;
    const { duration = 3000, type = 'info' } = options;

    const assertedFlashContainer = /** @type {HTMLElement} */ (flashContainer);

    // Create the new element
    const flashElement = document.createElement('li');
    flashElement.className = 'flash-item';
    flashElement.classList.add(`flash-item--${type}`); // e.g., flash-item--error
    flashElement.innerHTML = message;


    assertedFlashContainer.appendChild(flashElement);

    // Force reflow, then trigger fade-in animation
    // This ensures the transition from opacity 0 -> 1 always plays.
    void flashElement.offsetWidth;
    flashElement.classList.add('flash-item--visible');

    const remove = () => {
        flashElement.classList.remove('flash-item--visible');
        flashElement.addEventListener('transitionend', () => {
            flashElement.remove();
        }, { once: true });
    };

    if (duration > 0) {
        // Auto-remove after duration
        setTimeout(remove, duration);
        return null;
    } else {
        // Return the remover function to the caller
        return remove;
    }
}


/**
 * Sets up all site-wide event listeners for automatically triggering flash messages.
 *
 * It attaches listeners for:
 * - The custom 'flashMessage' event (e.g., sent from the server via HTMX).
 * - The 'htmx:responseError' event to automatically flash error details.
 * - An initial page load, checking for a 'data-flash-message' attribute
 * on the '.flash-message' element.
 *
 * This should be called once on application startup.
 *
 * For manually triggering a flash message, import and call the `flash()`
 * function directly.
 *
 * @returns {void}
 */
export function registerFlashListeners() {
    // Listen for the flashMessage event from the server

    document.body.addEventListener('flashMessage', (event) => {
        const customEvent = /** @type {CustomEvent<{value: string}>} */ (event);

        flash(customEvent.detail.value, { duration: 3000 });
    });

    // Listen for the response error event from the server
    document.body.addEventListener('htmx:responseError', function(event) {
        const customEvent = /** @type {CustomEvent<{xhr: XMLHttpRequest}>} */ (event);

        const xhr = customEvent.detail.xhr;
        let errorMessage = xhr.responseText; // Default to the raw response

        // Try to parse the response as JSON
        try {
            const errorObject = JSON.parse(xhr.responseText);
            // If parsing succeeds and a 'detail' key exists, use that.
            if (errorObject && errorObject.detail) {
                errorMessage = errorObject.detail;
            }
        } catch (e) {}

        // Display the flash as error type
        flash(errorMessage, { duration: 5000, type: 'error' });
    });

    // Check if the server loaded the page with a flash message to display
    document.addEventListener('DOMContentLoaded', () => {
        // Find the flash container
        const flashContainer = document.querySelector('.flash-container');
        if (!(flashContainer instanceof HTMLElement)) throw new Error("Critical element .flash-container is missing!");

        // Check if the data attribute exists
        const message = flashContainer.dataset.flashMessage;
        if (message) {
            flash(message, { duration: 3000 });

            // Cleanup dataset
            delete flashContainer.dataset.flashMessage;
        }
    });
}