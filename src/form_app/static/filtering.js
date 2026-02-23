<script>
    document.addEventListener('DOMContentLoaded', function() {
    const filterButtons = document.querySelectorAll('#match-filters button');
    const matchItems = document.querySelectorAll('.match-item');

    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            // 1. Remove 'active' class from all buttons
            filterButtons.forEach(btn => btn.classList.remove('active'));
            // 2. Add 'active' class to clicked button
            button.classList.add('active');

            const filterValue = button.getAttribute('data-filter');

            matchItems.forEach(item => {
                const itemStatus = item.getAttribute('data-status');

                // Logic: 
                // If filter is 'all', show everything.
                // Otherwise, check if item's status matches the filter.
                // Note: You might need to adjust logic if one button maps to multiple DB statuses
                if (filterValue === 'all' || itemStatus === filterValue) {
                    item.style.display = 'block'; // Or 'flex' depending on your layout, but block works for Bootstrap cols
                } else {
                    item.style.display = 'none';
                }
            });
        });
    });
});
</script>