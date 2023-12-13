// customer_dashboard.js
import { updateWeekData, updateWeekShiftContext, fetchOrderHistory, fetchUserGoals } from './userInteraction.js';
import { initMap, loadGeoJsonData } from './map.js';
import { addIndividualMealToCart, addAllMealsToCart, addToCart } from './mealCart.js';


document.addEventListener("DOMContentLoaded", function() {
    // Initialize current week shift state
    let currentWeekShift = 0;

    // Event listeners for week navigation
    document.getElementById('prev-week-link').addEventListener('click', (event) => {
        event.preventDefault();
        currentWeekShift -= 1;
        updateWeekData(currentWeekShift);
        updateWeekShiftContext(currentWeekShift);
    });

    document.getElementById('next-week-link').addEventListener('click', (event) => {
        event.preventDefault();
        currentWeekShift += 1;
        updateWeekData(currentWeekShift);
        updateWeekShiftContext(currentWeekShift);
    });

    // Initial data fetch and setup
    updateWeekData(currentWeekShift);
    fetchOrderHistory(currentWeekShift);
    fetchUserGoals();
    initMap();


    // Event listener for 'Add to Cart' buttons
    document.addEventListener('click', function(event) {
        if (event.target.matches('.add-individual-meal-to-cart-btn')) {
            const mealId = event.target.dataset.mealId;
            const partySize = event.target.closest('.meal-plan-item').querySelector('.party-size-input').value;
            addIndividualMealToCart(mealId, partySize);
        }

        if (event.target.matches('.add-all-meals-to-cart-btn')) {
            const mealPlanId = event.target.dataset.mealPlanId;
            addAllMealsToCart(mealPlanId);
        }

        if (event.target.matches('.add-to-cart-btn')) {
            const mealId = event.target.dataset.mealId;
            const partySize = event.target.closest('.meal-plan-item').querySelector('.party-size-input').value;
            addToCart(mealId, partySize);
        }
    });
});
