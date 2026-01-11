async function initAutocomplete() {
    // 1. WAIT for the library to load. 
    // This connects to the snippet you pasted in HTML.
    const { Autocomplete } = await google.maps.importLibrary("places");

    // 2. Loop through your inputs (same logic as before)
    ['1', '2'].forEach(i => {
        const nameInput = document.getElementById(`place_input_${i}`);
        const idInput = document.getElementById(`place_id_${i}`);

        if (nameInput && idInput) {
            // 3. Use the imported 'Autocomplete' class directly
            const autocomplete = new Autocomplete(nameInput, {
                types: ['restaurant'],
                fields: ['place_id', 'name', 'formatted_address'],
                componentRestrictions: { country: "tw" },
            });

            autocomplete.addListener('place_changed', () => {
                const place = autocomplete.getPlace();

                if (!place.place_id) {
                    idInput.value = "";
                    return;
                }

                // Update Hidden ID and Visible Name
                idInput.value = place.place_id;
                nameInput.value = place.name;
            });

            // Clear ID if user modifies text
            nameInput.addEventListener('input', () => {
                idInput.value = "";
            });
        }
    });
}

// 4. Trigger the async function immediately
initAutocomplete();
