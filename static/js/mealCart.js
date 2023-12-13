// mealCart.js

function addIndividualMealToCart(mealId, partySize) {
    fetch(`/meals/add_individual_meal_to_cart/${mealId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'), // Assuming you have a function to get CSRF token
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `party_size=${encodeURIComponent(partySize)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Individual meal added to cart');
            // Update UI here
        } else {
            console.error('Failed to add individual meal to cart:', data.message);
        }
    })
    .catch(error => {
        console.error('Error adding individual meal to cart:', error);
    });
}

// Function to add all meals to cart
function addAllMealsToCart(mealPlanId) {
    let mealInfos = [];
    document.querySelectorAll('.meal-plan-item').forEach(item => {
        const mealId = item.dataset.mealId;
        const partySize = item.querySelector('.party-size-input').value;
        mealInfos.push(`${mealId},${partySize}`);
    });

    fetch('/meals/add_all_to_cart/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `meal_info[]=${encodeURIComponent(mealInfos.join('&meal_info[]='))}` // This creates a query string for an array
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Failed to add all meals to cart');
        }
    })
    .then(data => {
        console.log('All meals added to cart');
        // Update UI here
    })
    .catch(error => {
        console.error('Error adding all meals to cart:', error);
    });
}


function addToCart(mealId, partySize) {
    const formData = new URLSearchParams();
    formData.append('meal_id', mealId);
    formData.append('party_size', partySize);

    fetch(`/meals/add_to_cart/${mealId}/${partySize}`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'), // Assuming you have a function to get CSRF token
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Meal added to cart');
            // Update UI to reflect the item added to the cart
        } else {
            console.error('Failed to add meal to cart:', data.message);
        }
    })
    .catch(error => {
        console.error('Error adding meal to cart:', error);
    });
}

// Export functions if using modules
export { addIndividualMealToCart, addAllMealsToCart, addToCart };
