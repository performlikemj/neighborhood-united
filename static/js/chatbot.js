    // chatbot.js
    import {getCookie} from './userInteraction.js';

    // Setup chat with GPT Assistant
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatBox = document.getElementById('chat-box');
    let threadId = document.getElementById('thread-id').value; // Get the current thread ID



    chatForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const question = chatInput.value;
        threadId = document.getElementById('thread-id').value; // Get the current thread ID
        displayUserQuestion(question); // Display user question immediately
        chatInput.value = ''; // Clear the input after sending
        sendQuestionToAssistant(question, threadId);
    });

    function displayUserQuestion(question) {
        const questionElement = document.createElement('div');
        questionElement.classList.add('message', 'user');
        questionElement.textContent = `You: ${question}`;
        chatBox.appendChild(questionElement);
        chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom
    }



    async function sendQuestionToAssistant(question) {
        try {
            const requestBody = threadId ? { question, thread_id: threadId } : { question };
            const response = await fetch('/customer_dashboard/api/chat_with_gpt/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            const data = await response.json();
    
            // Update the currentThreadId with the new_thread_id from the response
            if (data.new_thread_id) {
                document.getElementById('thread-id').value = data.new_thread_id; // Store the new thread ID
            }
    
            displayAssistantResponse(data);
        } catch (error) {
            console.error('Error sending question to assistant:', error);
            displayAssistantResponse({ messages: [] });
        }
    }


    function createDishesTable(dishes) {
        let table = document.createElement('table');
        let thead = table.createTHead();
        let tbody = table.createTBody();

        // Create the header
        let headerRow = thead.insertRow();
        let headers = ["Meal ID", "Name", "Chef", "Start Date", "End Date", "Availability", "Dishes"];
        headers.forEach(headerText => {
            let header = document.createElement("th");
            header.textContent = headerText;
            headerRow.appendChild(header);
        });

        // Create the body rows
        dishes.forEach(dish => {
            let row = tbody.insertRow();

            // Add Meal ID as a link
            let cell = row.insertCell();
            let mealIdLink = document.createElement('a');
            mealIdLink.href = `/meals/meal_detail/${dish.meal_id}/`; // Adjust the URL pattern as needed
            mealIdLink.textContent = dish.meal_id;
            cell.appendChild(mealIdLink);

            // Add Name
            cell = row.insertCell();
            cell.textContent = dish.name;

            // Add Chef with a link to their profile
            cell = row.insertCell();
            if (dish.chefs.length > 0) {
                let chefLink = document.createElement('a');
                chefLink.href = `/chefs/${dish.chefs[0].id}/`; // Link to chef's profile
                chefLink.textContent = dish.chefs[0].name;
                cell.appendChild(chefLink);
            } else {
                cell.textContent = 'N/A';
            }

            // Add Start Date
            cell = row.insertCell();
            cell.textContent = dish.start_date;


            // Add Availability
            cell = row.insertCell();
            cell.textContent = dish.is_available ? "Available" : "Not Available";

            // Add Dishes
            cell = row.insertCell();
            let dishNames = dish.dishes.map(d => d.name).join(", ");
            cell.textContent = dishNames;
        });

        return table;
    }

    function createMealPlanTable(mealPlans) {
        let table = document.createElement('table');
        table.classList.add('meal-plan-table');

        let thead = table.createTHead();
        let tbody = table.createTBody();

        // Create the header
        let headerRow = thead.insertRow();
        let headers = ["Meal ID", "Name", "Chef", "Start Date", "End Date", "Availability", "Dishes"];
        headers.forEach(headerText => {
            let header = document.createElement("th");
            header.textContent = headerText;
            headerRow.appendChild(header);
        });

        // Create the body rows
        mealPlans.forEach(mealPlan => {
            let row = tbody.insertRow();

            // Add Meal ID
            row.insertCell().textContent = mealPlan.meal_id;

            // Add Name
            row.insertCell().textContent = mealPlan.name;

            // Add Chef
            row.insertCell().textContent = mealPlan.chef;

            // Add Start Date
            row.insertCell().textContent = mealPlan.start_date;


            // Add Availability
            row.insertCell().textContent = mealPlan.is_available ? "Available" : "Not Available";

            // Add Dishes
            let dishesCell = row.insertCell();
            dishesCell.textContent = Array.isArray(mealPlan.dishes) ? mealPlan.dishes.join(", ") : 'N/A';
        });

        return table;
    }

    function displayAssistantResponse(data) {
        const chatBox = document.getElementById('chat-box');
    
        // Display the assistant's text response
        const responseElement = document.createElement('pre');
        responseElement.classList.add('message', 'assistant');
        if (data.last_assistant_message) {
            // Replace **text** with <strong>text</strong>
            const formattedMessage = data.last_assistant_message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            responseElement.textContent = `Assistant: ${formattedMessage}`;
            chatBox.appendChild(responseElement);
        } else {
            responseElement.textContent = "Assistant: No response received.";
            chatBox.appendChild(responseElement);
        }
    
        // Clear existing galleries
        document.querySelectorAll('.meal-gallery, .chef-gallery').forEach(element => element.remove());
    
        // Display galleries for dishes, chefs, and meal plans if available
        if (data.formatted_outputs && data.formatted_outputs.length > 0) {
            const galleriesContainer = document.createElement('div');
            galleriesContainer.id = 'galleries-container';
            document.getElementById('chat-section').appendChild(galleriesContainer);
    
            data.formatted_outputs.forEach(formattedOutput => {
                const outputData = JSON.parse(formattedOutput.output);
    
                if (outputData.auth_dish_result) {
                    displayDishes(outputData.auth_dish_result, 'Search Results', galleriesContainer);
                }
                if (outputData.auth_chef_result) {
                    displayChefs(outputData.auth_chef_result, 'Authenticated Chef Results', galleriesContainer);
                }
                if (outputData.suggested_meal_plan && outputData.suggested_meal_plan.auth_meal_plan) {
                    displayMealPlans(outputData.suggested_meal_plan.auth_meal_plan, 'Authenticated Suggested Meal Plans', galleriesContainer);
                    console.log('Storing meal plan:', outputData.suggested_meal_plan.auth_meal_plan);
                    storeMealPlan(outputData.suggested_meal_plan.auth_meal_plan); // Store the meal plan
                    displayMealPlans(getStoredMealPlan(), 'Authenticated Meal Plans', galleriesContainer);
                }
                if (outputData.auth_meal_plan && !outputData.auth_chef_result && !outputData.auth_dish_result && !outputData.guest_chef_result && !outputData.guest_dish_result) {
                    displayMealPlans(outputData.auth_meal_plan, 'Authenticated Meal Plans', galleriesContainer);
                    storeMealPlan(outputData.auth_meal_plan); // Store the meal plan
                }
            });
        }
    
        // Scroll to the latest message
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function displayDishes(dishes, title) {
        const gallerySection = document.createElement('div');
        gallerySection.className = 'meal-gallery';
    
        const titleElement = document.createElement('h2');
        titleElement.textContent = title;
        gallerySection.appendChild(titleElement);
    
        const rowDiv = document.createElement('div');
        rowDiv.className = 'row';
    
        dishes.forEach(dish => {
            const colDiv = document.createElement('div');
            colDiv.className = 'col-md-4';
    
            const cardDiv = document.createElement('div');
            cardDiv.className = 'card';
    
            // Assuming there's an image URL for the dish
            const img = document.createElement('img');
            img.src = dish.image_url;
            img.className = 'card-img-top';
            img.alt = dish.name;
            cardDiv.appendChild(img);
    
            const cardBody = document.createElement('div');
            cardBody.className = 'card-body';
    
            const cardTitle = document.createElement('h5');
            cardTitle.className = 'card-title';
            cardTitle.textContent = dish.name;
            cardBody.appendChild(cardTitle);
    
            // Add chef details
            dish.chefs.forEach(chef => {
                const chefName = document.createElement('p');
                chefName.textContent = `Chef: ${chef.name}`;
                cardBody.appendChild(chefName);
            });
    
            // Add other dish details here
            // ...
    
            cardDiv.appendChild(cardBody);
            colDiv.appendChild(cardDiv);
            rowDiv.appendChild(colDiv);
        });
    
        gallerySection.appendChild(rowDiv);
        document.getElementById('chat-section').appendChild(gallerySection); // Append to the chat section or another appropriate element
    }


    function displayChefs(chefs, title) {
        const gallerySection = document.createElement('div');
        gallerySection.className = 'chef-gallery';

        const titleElement = document.createElement('h2');
        titleElement.textContent = title;
        gallerySection.appendChild(titleElement);

        const rowDiv = document.createElement('div');
        rowDiv.className = 'row';

        chefs.forEach(chef => {
            const colDiv = document.createElement('div');
            colDiv.className = 'col-md-4';

            const cardDiv = document.createElement('div');
            cardDiv.className = 'card';

            // Add chef profile picture if available
            if (chef.profile_pic) {
                const img = document.createElement('img');
                img.src = chef.profile_pic;
                img.className = 'card-img-top';
                img.alt = `Chef ${chef.name}`;
                cardDiv.appendChild(img);
            }

            const cardBody = document.createElement('div');
            cardBody.className = 'card-body';

            const cardTitle = document.createElement('h5');
            cardTitle.className = 'card-title';
            cardTitle.textContent = chef.name;
            cardBody.appendChild(cardTitle);

            const experienceText = document.createElement('p');
            experienceText.className = 'card-text';
            experienceText.textContent = `Experience: ${chef.experience} years`;
            cardBody.appendChild(experienceText);

            const bioText = document.createElement('p');
            bioText.className = 'card-text';
            bioText.textContent = chef.bio;
            cardBody.appendChild(bioText);

            // Add more details if available
            // ...

            cardDiv.appendChild(cardBody);
            colDiv.appendChild(cardDiv);
            rowDiv.appendChild(colDiv);
        });

        gallerySection.appendChild(rowDiv);
        document.getElementById('chat-section').appendChild(gallerySection);
    }


    function displayMealPlans(mealPlans, title) {
        // Clear existing meal plans
        document.querySelectorAll('.meal-gallery').forEach(element => element.remove());
    
        const gallerySection = document.createElement('div');
        gallerySection.className = 'meal-gallery';
    
        const titleElement = document.createElement('h2');
        titleElement.textContent = title;
        gallerySection.appendChild(titleElement);

        // Add the Approve Meal Plan button at the bottom
        const approveButton = document.createElement('button');
        approveButton.className = 'btn';
        approveButton.textContent = 'Approve Meal Plan';
        approveButton.onclick = function() {
            window.location.href = document.querySelector('div[data-approve-meal-plan-url]').dataset.approveMealPlanUrl;
        };
        gallerySection.appendChild(approveButton);
    
        // Group meals by day
        const mealsByDay = groupMealsByDay(mealPlans);
    
        Object.keys(mealsByDay).forEach(day => {
            const dayDiv = document.createElement('div');
            dayDiv.className = 'day-slot';
            dayDiv.innerHTML = `<h3>${day}</h3>`;
    
            mealsByDay[day].forEach(meal => {
                const mealDiv = document.createElement('div');
                mealDiv.className = 'meal-slot';
                mealDiv.innerHTML = `<p>${meal.name} by ${meal.chef}</p>`;
    
                // Add Customize and Remove buttons
                const customizeButton = createButton('Customize', () => showMealOptions(meal.meal_id, day));
                const removeButton = createButton('Remove', () => removeMealFromDay(meal.meal_id, day, meal.meal_plan_id));
                mealDiv.appendChild(customizeButton);
                mealDiv.appendChild(removeButton);
    
                dayDiv.appendChild(mealDiv);
    
                // Fetch and display meal details
                fetchMealDetails(meal.meal_id, mealDiv);
            });
    
            gallerySection.appendChild(dayDiv);
        });
    
        // Add the Submit Changes button at the bottom
        const submitButton = createButton('Submit Changes', submitMealPlanUpdates);
        submitButton.id = 'submit-meal-plan';
        gallerySection.appendChild(submitButton);
    
        document.getElementById('chat-section').appendChild(gallerySection);
    }
    
    function groupMealsByDay(mealPlans) {
        const groupedMeals = {};
        mealPlans.forEach(meal => {
            if (!groupedMeals[meal.day]) {
                groupedMeals[meal.day] = [];
            }
            groupedMeals[meal.day].push(meal);
        });
        return groupedMeals;
    }
    
    function createButton(text, onClickFunction) {
        const button = document.createElement('button');
        button.className = 'btn';
        button.textContent = text;
        button.onclick = onClickFunction;
        return button;
    }

    
    async function fetchMealDetails(mealId, containerElement) {
        try {
            const response = await fetch(`/meals/api/get_meal_details/?meal_id=${mealId}`);
            const mealDetails = await response.json();
            // Call a function to render the meal details
            renderMealDetails(mealDetails, containerElement);
        } catch (error) {
            console.error('Error fetching meal details:', error);
        }
    }
    
    
    function renderMealDetails(mealDetails, container) {
        // Here, update the container with meal details
        // For example, add a paragraph for each detail
        const detailsParagraph = document.createElement('p');
        detailsParagraph.textContent = `Details: ${mealDetails.name}, Chef: ${mealDetails.chef}, Available: ${mealDetails.is_available}`;
        container.appendChild(detailsParagraph);
    }    

    function storeMealPlan(mealPlan) {
        console.log('Storing meal plan function:', mealPlan);
        if (!mealPlan || mealPlan.length === 0) {
            console.warn('Attempted to store an empty or invalid meal plan.');
            return;
        }
    
        try {
            const mealPlanString = JSON.stringify(mealPlan);
            sessionStorage.setItem('mealPlan', mealPlanString); // Using sessionStorage
            console.log('Stored meal plan in sessionStorage:', mealPlanString);
        } catch (error) {
            console.error('Error storing meal plan in sessionStorage:', error);
        }
    }
    
    
    function getStoredMealPlan() {
        try {
            const storedPlanString = sessionStorage.getItem('mealPlan'); // Using sessionStorage
            console.log('Retrieved stored plan string from sessionStorage:', storedPlanString);
            return storedPlanString ? JSON.parse(storedPlanString) : null;
        } catch (error) {
            console.error('Error parsing stored meal plan from sessionStorage:', error);
            return null;
        }
    }
    
    

    function clearStoredMealPlan() {
        sessionStorage.removeItem('mealPlan');
    }


    // Function to create and return a chef details element
    function createChefDetailsElement(chef) {
        const chefDetailsElement = document.createElement('div');
        const postalCodesList = chef.service_postal_codes.join(', ');

        let serviceAreaText = `Service Areas: ${postalCodesList}`;
        if (chef.serves_user_area) {
            serviceAreaText += ' (Your area is included!)';
        }

        chefDetailsElement.innerHTML = `
            <h2>Chef Details: ${chef.name}</h2>
            <p>Experience: ${chef.experience || 'N/A'}</p>
            <p>Bio: ${chef.bio || 'N/A'}</p>
            <p>${serviceAreaText}</p>
        `;
        return chefDetailsElement;
    }


    // Function to format the service areas from GeoJSON to a readable string
    function formatServiceAreas(serviceAreas) {
        if (!serviceAreas || !serviceAreas.features || serviceAreas.features.length === 0) {
            return 'Not specified';
        }

        // Example formatting: list out the city and state for each feature
        return serviceAreas.features.map(feature => {
            const props = feature.properties;
            return props.city ? `${props.city}, ${props.state}` : 'Unnamed area';
        }).join(', ');
    }



    // Update displayFormattedOutput to handle meal plan data
    function displayFormattedOutput(formattedOutput) {
        try {
            const outputData = JSON.parse(formattedOutput.output);
            if (outputData.result) {
                return createDishesTable(outputData.result);
            } else if (outputData.suggested_meal_plan) {
                return createMealPlanTable(outputData.suggested_meal_plan.result);
            }
            // Handle other outputs...
        } catch (e) {
            console.error('Error parsing tool output JSON data:', e);
        }
    }


    async function submitMealPlanUpdates() {
        const updatedMealPlan = getStoredMealPlan();
        console.log('Submitting meal plan updates:', updatedMealPlan);
    
        // Find the first meal that has a meal_plan_id and use it
        const mealWithPlanId = updatedMealPlan.find(meal => meal.meal_plan_id);
        const mealPlanId = mealWithPlanId ? mealWithPlanId.meal_plan_id : null;
    
        if (mealPlanId) {
            const updatedMealsWithId = updatedMealPlan.map(meal => ({ ...meal, meal_plan_id: mealPlanId }));
    
            try {
                const response = await fetch('/meals/api/submit_meal_plan/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ mealPlan: updatedMealsWithId })
                });
                const data = await response.json();
                if (data.status === 'success') {
                    console.log('Meal plan updated successfully.');
                    clearStoredMealPlan(); // Clear the local storage
                    // Update UI to show success message
                } else {
                    console.error('Error updating meal plan:', data.message);
                }
            } catch (error) {
                console.error('Error:', error);
            }
        } else {
            console.error('No meal_plan_id found. Cannot submit updates.');
        }
    }
    
    
    async function showMealOptions(mealId, day) {
        try {
            const response = await fetch(`/meals/api/get_alternative_meals/?day=${day}`);
            const data = await response.json();
            console.log(data);  // Log the response data for debugging
            const modalContent = document.getElementById('modal-content');
            modalContent.innerHTML = '';  // Clear previous content
    
            if (data.success) {
                data.meals.forEach(meal => {
                    let option = document.createElement('div');
                    option.textContent = meal.name;  // Display meal name
                    option.onclick = () => replaceMealForDay(mealId, meal.id, day);  // Replace meal on click
                    modalContent.appendChild(option);
                });
            } else {
                // Display the message if no meals are available
                let message = document.createElement('p');
                message.textContent = data.message;
                modalContent.appendChild(message);
            }
            // Show the modal
            $('#mealOptionsModal').modal('show');
        } catch (error) {
            console.error('Error fetching alternative meals:', error);
        }
    }
    
  
    
    function removeMealFromDay(mealId, day, mealPlanId) {
        // Update local storage
        let mealPlan = getStoredMealPlan();
        mealPlan = mealPlan.filter(meal => !(meal.meal_id === mealId && meal.day === day));
        storeMealPlan(mealPlan);
        displayMealPlans(mealPlan, 'Updated Meal Plan')
        // Update UI accordingly
    }
    
    
    async function replaceMealForDay(originalMealId, newMealId, day) {
        console.log(`Replace meal ${originalMealId} with ${newMealId} for ${day}`);
        let mealPlan = getStoredMealPlan();
        if (!mealPlan) {
            console.error('No stored meal plan found. Cannot replace meal.');
            return;
        }
    
        try {
            const response = await fetch(`/meals/api/get_meal_details/?meal_id=${newMealId}`);
            const newMealDetails = await response.json();
            mealPlan = mealPlan.map(meal => {
                if (meal.meal_id === originalMealId && meal.day === day) {
                    return {...newMealDetails, day: meal.day}; // Update all meal details
                }
                return meal;
            });
            console.log('Updated meal plan:', mealPlan);
            storeMealPlan(mealPlan);
            displayMealPlans(mealPlan, 'Updated Meal Plan');
        } catch (error) {
            console.error('Error fetching new meal details:', error);
        }
    }
    
    
    
    function addMealToDay(newMealId, day, mealPlanId) {
        console.log(`Add meal ${newMealId} to ${day}`);
        // Update local storage
        let mealPlan = getStoredMealPlan();
        mealPlan.push({ meal_id: newMealId, day });
        storedMealPlan(mealPlan);
        displayMealPlans(mealPlan, 'Updated Meal Plan')
        // Update UI to reflect the addition
    }
    


    // Export functions if using modules
    export { displayUserQuestion, sendQuestionToAssistant, displayAssistantResponse, createMealPlanTable, storeMealPlan, getStoredMealPlan, displayMealPlans };
