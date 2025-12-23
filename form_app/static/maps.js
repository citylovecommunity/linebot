async function initMap() {
    // Request needed libraries.
    await google.maps.importLibrary('places');

    // Get the existing input elements
    const place1Input = document.getElementById('place1');
    const place2Input = document.getElementById('place2');

    // Attach autocomplete to place1 input
    if (place1Input) {
        const autocomplete1 = new google.maps.places.Autocomplete(place1Input);
        autocomplete1.addListener('place_changed', () => {
            const place = autocomplete1.getPlace();
            // Construct Google Maps URL using place ID
            const url = `https://www.google.com/maps/place/?q=place_id:${place.place_id}`;
            place1Input.value = url;
            // Store the full place data in a hidden input for server processing
            let hidden1 = document.getElementById('place1_data');
            if (!hidden1) {
                hidden1 = document.createElement('input');
                hidden1.type = 'hidden';
                hidden1.id = 'place1_data';
                hidden1.name = 'place1_data';
                place1Input.parentNode.appendChild(hidden1);
            }
            hidden1.value = JSON.stringify(place);
        });
    }

    // Attach autocomplete to place2 input
    if (place2Input) {
        const autocomplete2 = new google.maps.places.Autocomplete(place2Input);
        autocomplete2.addListener('place_changed', () => {
            const place = autocomplete2.getPlace();
            // Construct Google Maps URL using place ID
            const url = `https://www.google.com/maps/place/?q=place_id:${place.place_id}`;
            place2Input.value = url;
            // Store the full place data in a hidden input for server processing
            let hidden2 = document.getElementById('place2_data');
            if (!hidden2) {
                hidden2 = document.createElement('input');
                hidden2.type = 'hidden';
                hidden2.id = 'place2_data';
                hidden2.name = 'place2_data';
                place2Input.parentNode.appendChild(hidden2);
            }
            hidden2.value = JSON.stringify(place);
        });
    }
}

initMap();