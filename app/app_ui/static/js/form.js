// Defensive: attach only when DOM ready and form exists. Do not throw if element missing.
document.addEventListener('DOMContentLoaded', function () {
    var formEl = document.getElementById('predictionForm');
    if (!formEl) return; // nothing to validate on pages without the form

    formEl.addEventListener('submit', function(event) {
        try {
            var form = event.target;
            var errorMessages = [];

            // Only validate elements that are explicitly marked required.
            var fields = form.querySelectorAll('[required]');
            fields.forEach(function(field) {
                var val = field.value;
                if (!val || (field.type === 'number' && isNaN(Number(val)))) {
                    errorMessages.push((field.name || field.id || 'field') + ' is required.');
                }
            });

            if (errorMessages.length > 0) {
                event.preventDefault();
                // Keep UX minimal and avoid blocking with native alert in modern flows.
                // If a toast system exists, use it; otherwise fall back to alert.
                if (window.showToast) {
                    showToast('Please fill in required fields: ' + errorMessages.join(', '), 'warning');
                } else {
                    alert('Please fill in the following fields correctly:\n' + errorMessages.join('\n'));
                }
            }
        } catch (err) {
            // Defensive fallback: do not block submission on unexpected errors
            console.error('Form validation error (non-fatal):', err);
        }
    });
});