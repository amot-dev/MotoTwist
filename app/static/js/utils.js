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