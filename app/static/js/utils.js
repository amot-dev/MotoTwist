// Get the computed styles from the root element (the <html> tag)
const rootStyles = getComputedStyle(document.documentElement);
const accentBlue = rootStyles.getPropertyValue('--accent-blue').trim();
const accentBlueHoverLight = rootStyles.getPropertyValue('--accent-blue-hover-light').trim();
const accentOrange = rootStyles.getPropertyValue('--accent-orange').trim();

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

// Check if the server loaded the page with a flash message to display
document.addEventListener('DOMContentLoaded', () => {
    // Check if the data attribute exists
    flashMessage = document.querySelector('.flash-message')
    const message = flashMessage.dataset.flashMessage;

    if (message) {
        flash(message, 3000);

        // Cleanup dataset
        delete flashElement.dataset.flashMessage;
    }
});

document.body.addEventListener('click', function(event) {
    // Find the button that was clicked
    const copyButton = event.target.closest('.button-copy-input');

    // If a copy button wasn't clicked or it's already copied, do nothing
    if (!copyButton || copyButton.classList.contains('copied')) {
        return;
    }

    // Find the target input field using the button's data attribute
    const targetId = copyButton.dataset.targetId;
    const inputField = document.getElementById(targetId);
    if (!inputField) {
        return;
    }

    // Use the modern Clipboard API to copy the input's value
    navigator.clipboard.writeText(inputField.value).then(() => {
        // --- Success! Provide feedback ---
        const icon = copyButton.querySelector('i');
        if (icon) {
            icon.classList.remove('fa-copy');
            icon.classList.add('fa-check');
        }
        copyButton.classList.add('copied');

        // Reset the button after 2 seconds
        setTimeout(() => {
            if (icon) {
                icon.classList.remove('fa-check');
                icon.classList.add('fa-copy');
            }
            copyButton.classList.remove('copied');
        }, 2000);

    }).catch(err => {
        console.error('Failed to copy text: ', err);
    });
});