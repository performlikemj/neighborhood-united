// main.js
import { initMap, loadGeoJsonData } from './map.js';
import { 
    getCookie, fetchOrderHistory, fetchUserGoals, 
    submitFoodPreferencesForm, handleGoalsFormSubmit, fetchUserHistory, fetchFoodPreferencesData, populateFoodPreferencesForm
} from './userInteraction.js';
import { displayUserQuestion, sendQuestionToAssistant, displayAssistantResponse } from './chatbot.js';
import { addIndividualMealToCart, addAllMealsToCart, addToCart } from './mealCart.js';

document.addEventListener("DOMContentLoaded", function() {
    // Initialization code here...
    fetchOrderHistory(0);
    fetchUserGoals();
    fetchFoodPreferencesData();
    fetchUserHistory();

    // Event listener for food preferences form submission
    const preferencesForm = document.getElementById('preferences-form');
    if(preferencesForm) {
        preferencesForm.addEventListener('submit', event => submitFoodPreferencesForm(event));
    }

    // Event listener for goals form submission
    const goalsForm = document.getElementById('goals-form');
    if(goalsForm) {
        goalsForm.addEventListener('submit', handleGoalsFormSubmit);
    }

    // Get the elements
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarExpand = document.getElementById('sidebar-expand');

    // Event listener for the button inside the sidebar
    sidebarToggle.addEventListener('click', function() {
        // Hide the sidebar
        sidebar.classList.add('d-none');
        // Show the collapsed sidebar button
        sidebarExpand.parentElement.classList.remove('d-none');
    });

    // Event listener for the button outside the sidebar
    sidebarExpand.addEventListener('click', function() {
        // Show the sidebar
        sidebar.classList.remove('d-none');
        // Hide the collapsed sidebar button
        sidebarExpand.parentElement.classList.add('d-none');
    });
});



// ... Rest of your main JavaScript code ...
