// userInteraction.js


function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function updateWeekData(weekShift) {
    // Fetch and update order history for the given week shift
    fetchOrderHistory(weekShift);

 

    // Any other updates that need to happen when the week changes
    // ...
}

function updateDateRangeDisplay(start, end) {
    let dateRangeElement = document.getElementById('history-section').getElementsByTagName('h2')[0];
    dateRangeElement.innerHTML = `Your Orders for (${start} - ${end})`;
}

function updateWeekShiftContext(weekShift) {
    fetch('/customer_dashboard/api/update_week_shift/', {  
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),  // Ensure CSRF token is included
        },
        body: JSON.stringify({ week_shift: weekShift }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log('Week shift context updated successfully:', data);
    })
    .catch(error => {
        console.error('Failed to update week shift context:', error);
    });
}

function fetchOrderHistory(weekShift) {
    fetch(`/customer_dashboard/api/order_history/?week_shift=${weekShift}`)
        .then(response => response.json())
        .then(data => {
            let tbody = document.getElementById('order-history-tbody');
            // Check if orders_html is defined and is a string
            if (typeof data.orders_html === 'string') {
                tbody.innerHTML = data.orders_html; // Insert HTML directly
            } else {
                console.error('Unexpected response:', data);
            }
            updateDateRangeDisplay(data.current_week_start, data.current_week_end);
        })
        .catch(error => {
            console.error('Error fetching order history:', error);
        });
  }



 // Function to toggle edit state
 function toggleEditState(mealPlanMealId) {
    const row = document.getElementById(`meal-plan-meal-${mealPlanMealId}`);
    const isEditable = row.classList.contains('editable');
    
    if (isEditable) {
    // Switch from edit state to view state
    // Save the changes if any
    updateMealPlanDetails(mealPlanMealId);
    } else {
    // Switch from view state to edit state
    // Convert text to input fields
    makeRowEditable(row);
    }

    row.classList.toggle('editable');
}

// Function to make a row editable
function makeRowEditable(row) {
    const cells = row.getElementsByTagName('td');
    for (let cell of cells) {
    if (cell.dataset.type === 'meal') {
        const oldValue = cell.innerText;
        cell.innerHTML = `<input type='text' value='${oldValue}'>`;
    }
    }
}

function updateMealPlanDetails(mealPlanMealId) {
    const row = document.getElementById(`meal-plan-meal-${mealPlanMealId}`);
    const cells = row.getElementsByTagName('td');
    let newMealValue;

    for (let cell of cells) {
    if (cell.dataset.type === 'meal') {
        newMealValue = cell.getElementsByTagName('input')[0].value;
        // Optionally, revert the input back to text if you wish to show it's been saved
        cell.innerText = newMealValue;
    }
    }

    // Prepare data to send in the POST request
    const formData = new FormData();
    formData.append('meal_plan_id', mealPlanMealId);
    formData.append('new_meal_value', newMealValue);

    // Use fetch to send a POST request to update the meal plan details
    fetch('/customer_dashboard/api/api_meal_plan_details/', {
    method: 'POST',
    body: formData,
    // Include headers and other necessary configurations, such as CSRF tokens
    })
    .then(response => response.json())
    .then(data => {
    // Handle the response data
    // For example, update the UI to show that the update was successful
    console.log('Update successful', data);
    })
    .catch(error => {
    // Handle errors
    console.error('Error updating meal plan details:', error);
    });
}


function fetchUserHistory() {
    fetch('/customer_dashboard/api/history/')
    .then(response => response.json())
    .then(data => {
        console.log('User history:', data);
        let historySubmenu = document.getElementById('historySubmenu');
        let threads = JSON.parse(data.chat_threads); // Parse the JSON string to get the threads array
        threads.forEach(thread => {
            let threadElement = document.createElement('a');
            threadElement.href = `/customer_dashboard/history/${thread.fields.openai_thread_id}/`; // Accessing 'fields' object for model fields
            threadElement.textContent = `${thread.fields.title} - ${new Date(thread.fields.created_at).toLocaleDateString()}`;
            historySubmenu.appendChild(threadElement);
        });
    })
    .catch(error => {
        console.error('Error fetching user history:', error);
    });
}



function fetchFoodPreferencesData() {
    fetch('/customer_dashboard/api/food_preferences/')
    .then(response => response.json())
    .then(data => {
        populateFoodPreferencesForm(data.preferences, data.choices);
    })
    .catch(error => console.error('Error fetching food preferences:', error));
}

function populateFoodPreferencesForm(preferences, choices) {
    let formElement = document.getElementById('food-preferences-form');
    
    // Clear existing contents of the form
    formElement.innerHTML = '';

    // Loop through the choices and create checkboxes
    Object.entries(choices).forEach(([value, label]) => {
        // Create a container for each checkbox
        let container = document.createElement('div');
        container.className = 'form-check';

        // Create the checkbox
        let checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'form-check-input';
        checkbox.id = 'pref-' + value;
        checkbox.name = 'dietary_preference';
        checkbox.value = value;

        // Check the checkbox if the user has this preference
        if (preferences.dietary_preference === value) {
            checkbox.checked = true;
        }

        // Create a label for the checkbox
        let checkboxLabel = document.createElement('label');
        checkboxLabel.className = 'form-check-label';
        checkboxLabel.htmlFor = 'pref-' + value;
        checkboxLabel.textContent = label;

        // Append checkbox and label to the container
        container.appendChild(checkbox);
        container.appendChild(checkboxLabel);

        // Append the container to the form
        formElement.appendChild(container);
    });

    // Append a submit button to the form
    let submitButton = document.createElement('button');
    submitButton.type = 'submit';
    submitButton.className = 'btn btn-primary';
    submitButton.textContent = 'Save Preferences';
    formElement.appendChild(submitButton);
}


function submitFoodPreferencesForm(formElement) {
    const formData = new FormData(formElement);
    let data = {};
    formData.forEach((value, key) => { data[key] = value });

    fetch('/customer_dashboard/api/update_food_preferences/', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
    })
    .then(response => response.json())
    .then(data => {
        // Handle success or error
        // ...
    })
    .catch(error => console.error('Error submitting food preferences form:', error));
}



function fetchUserGoals() {
    fetch('/customer_dashboard/api/track_goals/')
    .then(response => response.json())
    .then(data => {
        let goalsContainer = document.getElementById('goals-container');
        let goalElement = document.createElement('div');
        
    })
    .catch(error => {
        console.error('Error fetching user goals:', error);
    });
}


function handleGoalsFormSubmit(event) {
    event.preventDefault();
    const formData = new FormData(event.target);

    fetch('/customer_dashboard/api/update_goal/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            fetchUserGoals(); // Refetch goals to update the sidebar
        } else {
            // Handle error
        }
    })
    .catch(error => console.error('Error updating goals:', error));
}





// Export functions if using modules
export { 
    getCookie, updateWeekData, updateDateRangeDisplay, 
    updateWeekShiftContext, fetchOrderHistory, 
    toggleEditState, makeRowEditable, updateMealPlanDetails, fetchUserGoals, fetchFoodPreferencesData, populateFoodPreferencesForm, submitFoodPreferencesForm, handleGoalsFormSubmit, fetchUserHistory,

};
