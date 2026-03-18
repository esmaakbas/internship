document.getElementById('predictionForm').addEventListener('submit', function(event) {
    var form = event.target;
    var errorMessages = [];
    
    var fields = form.querySelectorAll('[required]');
    fields.forEach(function(field) {
        if (!field.value || (field.type === 'number' && isNaN(field.value))) {
            errorMessages.push(`${field.name} is required.`);
        } 
    });

    if (errorMessages.length > 0) {
        event.preventDefault();
        alert("Please fill in the following fields correctly:\n" + errorMessages.join("\n"));
    }
});