import { initMap } from './map.js';
import { registerTwistListeners } from './displayTwist.js';
import {
    overrideXHR,
    registerTwistCreationListeners
} from './createTwist.js';


/**
 * Sets up global event listeners for server-sent commands,
 * typically triggered via HTMX events.
 *
 * This function should be called once on application startup (e.g., in app.js)
 * to enable the server to remotely control client-side UI elements.
 *
 * It listens for:
 * - 'resetForm': Resets all modal forms on active modals.
 * - 'closeModal': Resets all modal forms on active modals,
 * then closes the modals.
 *
 * @returns {void}
 */
function registerServerCommandListeners() {
    // Listen for the custom event sent from the server when a form needs to be cleared
    document.body.addEventListener('resetForm', () => {
        const activeModals = document.querySelectorAll('.modal[open]');
        activeModals.forEach(modal => {
            /** @type {NodeListOf<HTMLFormElement>} */
            const forms = modal.querySelectorAll('.modal-form');
            forms.forEach(form => form.reset());
        });
    });

    // Listen for the custom event sent from the server when a modal needs to be closed
    document.body.addEventListener('closeModal', () => {
        /** @type {NodeListOf<HTMLDialogElement>} */
        const activeModals = document.querySelectorAll('.modal[open]');
        activeModals.forEach(modal => {
            /** @type {NodeListOf<HTMLFormElement>} */
            const forms = modal.querySelectorAll('.modal-form');
            forms.forEach(form => form.reset());

            modal.close();
        });
    });
}


const map = initMap();

registerServerCommandListeners();
registerTwistListeners(map);
registerTwistCreationListeners(map);
overrideXHR();