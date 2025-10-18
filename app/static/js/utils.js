/**
 * Delays invoking a function until after `delay`
 * milliseconds have elapsed since the last time it was invoked.
 *
 * @param {function} func The function to debounce.
 * @param {number} delay The number of milliseconds to delay.
 * @returns {function} The new debounced function.
 */
export function debounce(func, delay) {
    /** @type {number | undefined} */
    let timeoutId;

    /**
     * @this {any}
     * @param {any[]} args
     */
    return function(...args) {
        const context = this;
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(context, args);
        }, delay);
    };
}


/**
 * Gets a CSS custom property from the root.
 *
 * @param {string} propName --e.g., '--accent-blue'
 * @returns {string} The trimmed value.
 */
export function getRootProperty(propName) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(propName)
        .trim();
}


/**
 * Sets up a global click listener to handle copy-to-clipboard
 *  functionality for any element with the `.button-copy-link` class.
 *
 * The button is expected to have a `data-target-id` attribute
 * that specifies the `id` of the input field to copy from.
 *
 * This should be called once on application startup.
 *
 * @returns {void}
 */
export function registerCopyButtonListener() {
    document.body.addEventListener('click', function(event) {
        if (!(event.target instanceof Element)) return;

        // Find the button that was clicked
        /** @type {HTMLElement | null} */
        const copyButton = event.target.closest('.button-copy-link');

        // If a copy button wasn't clicked or it's already copied, do nothing
        if (!copyButton || copyButton.classList.contains('copied')) return;

        // Find the target input field using the button's data attribute
        const targetId = copyButton.dataset.targetId;
        if (!targetId) throw new Error("Critical element .button-copy-link is missing targetId data!");
        const inputField = document.getElementById(targetId);
        if (!inputField || !(inputField instanceof HTMLInputElement)) {
            throw new Error("Critical target element referenced by .button-copy-link is missing or not an <input>!");
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
}


/**
 * Serializes all of a form's data into a URL-encoded string.
 * This creates a lightweight "snapshot" of the form's current state,
 * ideal for comparing against an original state to detect changes.
 *
 * @param {HTMLFormElement} formElement The <form> element to serialize.
 * @returns {string} A URL-encoded string of the form's data (e.g., "name=Test&email=test%40example.com").
 */
export function getFormDataAsString(formElement) {
    const formData = new FormData(formElement);

    /** @type {string[][]} */
    const entries = [];

    formData.forEach((value, key) => {
        // This ignores any File objects if they exist
        if (typeof value === 'string') {
            entries.push([key, value]);
        }
    });

    const params = new URLSearchParams(entries);
    return params.toString();
}


/**
 * The internal logic that finds and validates forms within a given element.
 * @param {Document | Element} [scope=document] - The element to search within for new forms.
 */
export function validateFormsInScope(scope = document) {
    /** @type {NodeListOf<HTMLFormElement>} */
    // Select all forms in scope that haven't been processed
    const forms = scope.querySelectorAll('form:not(.manual-validation):not(.validation-registered)');
    forms.forEach(form => {
        // Don't do anything if no submit button
        const submitButton = form.querySelector('button[type="submit"]');
        if (!(submitButton instanceof HTMLButtonElement)) return;

        // Add the marker class to prevent duplicate listeners
        form.classList.add('validation-registered');

        // Set the initial disabled state
        submitButton.disabled = !form.checkValidity();

        // Disable submit button if form is empty
        form.addEventListener('input', () => {
            submitButton.disabled = !form.checkValidity();
        });
    });
}