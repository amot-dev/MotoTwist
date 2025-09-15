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

// Listen for the flashMessage event from the server
document.body.addEventListener('flashMessage', (event) => {
    flash(event.detail.value, 3000);
});

// Listen for the response error event from the server
document.body.addEventListener('htmx:responseError', function(event) {
    const xhr = event.detail.xhr;
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
    flash(errorMessage, 5000, backgroundColor=accentOrange);
});

/**
 * Autofills a text input with the name of a selected file, minus its extension.
 *
 * This function is designed to be called from the 'onchange' event of a file
 * input. It only populates the target input if that field is currently empty,
 * preserving any value previously entered by the user.
 *
 * @param {HTMLElement} fileInput - The file input element that triggered the function.
 * @param {string} targetInputId - The ID of the text input field to populate.
 */
function autofillFromFilename(fileInput, targetInputId) {
    const nameInput = document.getElementById(targetInputId);

    // Only proceed if the file input has a file and the name field is empty
    if (fileInput.files.length > 0 && nameInput.value === '') {
        const fullFilename = fileInput.files[0].name;
        const nameWithoutExtension = fullFilename.replace(/\.[^/.]+$/, '');
        nameInput.value = nameWithoutExtension;
    }
}