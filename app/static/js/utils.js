/**
 * Displays a message in the flash message element for a set duration.
 * The function makes the flash element visible, sets its content,
 * and then fades it out after the specified duration.
 * @param {string} message - The message string to display. Can include HTML.
 * @param {number} duration - How long to display the message in ms before fading.
 * @param {string|null} [backgroundColor=null] - Optional background and border color for the flash message.
 * @param {string|null} [color=null] - Optional text color for the flash message.
 */
function flash(message, duration, backgroundColor=null, color=null) {
    // Exit early if the message is null, undefined, or empty
    if (!message) return;

    // Only proceed if the flash message element exists on the page
    const flashElement = document.querySelector('.flash-message');
    if (flashElement) {
        flashElement.innerHTML = message;
        flashElement.style.opacity = '1';
        flashElement.style.backgroundColor = backgroundColor;
        flashElement.style.borderColor = backgroundColor;
        flashElement.style.color = color;

        // Set a timer to hide the message after the specified duration
        setTimeout(() => {
            flashElement.style.opacity = null;

            // Only change non-opacity values after the transition is complete
            flashElement.addEventListener('transitionend', () => {
                flashElement.style.backgroundColor = null;
                flashElement.style.borderColor = null;
                flashElement.style.color = null;
            }, { once: true });
        }, duration);
    }
}