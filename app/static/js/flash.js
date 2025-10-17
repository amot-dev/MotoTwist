import { getRootProperty } from './utils.js';


const accentOrange = getRootProperty('--accent-orange');


/**
 * Displays a message in the flash message element for a set duration.
 * The function makes the flash element visible, sets its content,
 * and then fades it out after the specified duration.
 *
 * @param {string} message The message string to display. Can include HTML.
 * @param {number} duration How long to display the message in ms before fading.
 * @param {string} [backgroundColor=""] Optional background and border color for the flash message.
 * @param {string} [color=""] Optional text color for the flash message.
 */
export function flash(message, duration, backgroundColor="", color="") {
    // Exit early if the message is null, undefined, or empty
    if (!message) return;

    // Find the flash element
    const flashElement = document.querySelector('.flash-message');
    if (!flashElement || !(flashElement instanceof HTMLElement)) throw new Error("Critical element .flash-message is missing!");

    flashElement.innerHTML = message;
    flashElement.style.opacity = '1';
    flashElement.style.backgroundColor = backgroundColor;
    flashElement.style.borderColor = backgroundColor;
    flashElement.style.color = color;
    flashElement.style.pointerEvents = "auto";

    // Set a timer to hide the message after the specified duration
    setTimeout(() => {
        flashElement.style.opacity = "";

        // Only change non-opacity values after the transition is complete
        flashElement.addEventListener('transitionend', () => {
            flashElement.style.backgroundColor = "";
            flashElement.style.borderColor = "";
            flashElement.style.color = "";
            flashElement.style.pointerEvents = "";
        }, { once: true });
    }, duration);
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

        flash(customEvent.detail.value, 3000);
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

        // Display the flash with an orange accent
        flash(errorMessage, 5000, accentOrange);
    });

    // Check if the server loaded the page with a flash message to display
    document.addEventListener('DOMContentLoaded', () => {
        // Find the flash element
        const flashElement = document.querySelector('.flash-message');
        if (!flashElement || !(flashElement instanceof HTMLElement)) throw new Error("Critical element .flash-message is missing!");

        // Check if the data attribute exists
        const message = flashElement.dataset.flashMessage;
        if (message) {
            flash(message, 3000);

            // Cleanup dataset
            delete flashElement.dataset.flashMessage;
        }
    });
}