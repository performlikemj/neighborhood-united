// Function to get cookie by name
const getCookie = (name) => {
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
};

// Function to get session or local data
const getStorageData = () => {
  let storageType = isUserAuthenticated ? localStorage : sessionStorage;
  const storedData = storageType.getItem("qaData");
  return storedData ? JSON.parse(storedData) : [];
};

// Function to save to session or local storage
const saveToStorage = (data) => {
  let storageType = isUserAuthenticated ? localStorage : sessionStorage;
  try {
      storageType.setItem("qaData", JSON.stringify(data));
    } catch (e) {
      alert("Storage limit reached. Could not save data.");
      console.error("Storage limit reached. Could not save data.", e);
    }
  };

// Function to create a Bootstrap card
const createCard = (data, type) => {
  const card = document.createElement('div');
  card.classList.add('card', 'mb-3');

  const cardBody = document.createElement('div');
  cardBody.classList.add('card-body');

  const cardTitle = document.createElement('h5');
  cardTitle.classList.add('card-title');

  const cardText = document.createElement('p');
  cardText.classList.add('card-text');

  let cardLink;
  if (type === "chef") {
      cardTitle.textContent = `Chef: ${data.name}`;
      cardText.textContent = `Experience: ${data.experience}\nBio: ${data.bio}`;
      cardLink = document.createElement('a');
      cardLink.classList.add('btn', 'btn-primary');
      cardLink.href = `/chef/${data.id}`;
      cardLink.textContent = 'View Chef';
  } else if (type === "dish") {
      cardTitle.textContent = `Dish: ${data.name}`;
      cardText.textContent = `Ingredients: ${data.ingredients.join(", ")}`;
      cardLink = document.createElement('a');
      cardLink.classList.add('btn', 'btn-primary');
      cardLink.href = `/dish/${data.id}`;
      cardLink.textContent = 'View Dish';
  } else if (type === "meal_plan") {
      cardTitle.textContent = `Plan: ${data.name}`;
      cardText.textContent = `Chef: ${data.chef}\nStart: ${data.start_date}`;
      cardLink = document.createElement('a');
      cardLink.classList.add('btn', 'btn-primary');
      cardLink.href = `/meals/meal_detail/${data.meal_id}/`;
      cardLink.textContent = 'View Meal Plan';
  } else if (type === "ingredient") {
      cardTitle.textContent = `Ingredient: ${data.name}`;
      cardText.textContent = `Dishes: ${data.dishes.join(", ")}`;
      cardLink = document.createElement('a');
      cardLink.classList.add('btn', 'btn-primary');
      cardLink.href = `/ingredient/${data.id}`;
      cardLink.textContent = 'View Ingredient';
  }

  cardBody.appendChild(cardTitle);
  cardBody.appendChild(cardText);
  cardBody.appendChild(cardLink);
  card.appendChild(cardBody);

  return card;
};

// Function to add individual meal to cart
const addIndividualMealToCart = (mealId) => {
  fetch(`/meals/add_individual_meal_to_cart/${mealId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
    }
  }).then((response) => {
    if (response.ok) {
      alert('Meal added to cart!');
    } else {
      alert('Failed to add meal to cart');
    }
  });
};


// This function will loop through the meal plans and make AJAX calls to add them to the cart.
// Function to add all meals to cart
const addAllMealsToCart = (meals) => {
  meals.forEach((meal) => {
    fetch(`/meals/add_individual_meal_to_cart/${meal.meal_id}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
      }
    }).then((response) => {
      if (response.ok) {
        let addButton = document.getElementById('add-button');
        addButton.disabled = true;
      } else {
        alert('Failed to add meals to cart');
      }
    });
  });
};


// Function to add Query and Meal Plan to a single card
const addQueryAndMealPlanToCard = (question, answerData) => {
  const cardBody = document.createElement('div');
  let mealPlanText = "Suggested Meal Plan: ";

  if (Array.isArray(answerData.suggested_meal_plan)) {
      mealPlanText += answerData.suggested_meal_plan.map(plan => {
          return `Plan: ${plan.name}, Chef: ${plan.chef}, Start: ${plan.start_date}`;
      }).join('\n');

      const addAllButton = document.createElement('button');
      addAllButton.textContent = 'Add All to Cart';
      addAllButton.addEventListener('click', () => addAllMealsToCart(answerData.suggested_meal_plan));
      cardBody.appendChild(addAllButton);
      
      // Add individual "Add to Cart" buttons for each meal
      answerData.suggested_meal_plan.forEach((meal) => {
        const addButton = document.createElement('button');
        addButton.textContent = 'Add to Cart';
        addButton.addEventListener('click', () => addIndividualMealToCart(meal.meal_id));
        cardBody.appendChild(addButton);
      });
  } else {
      mealPlanText += answerData.suggested_meal_plan.message;
  }

  const card = createCard(`Question: ${question}`, `Answer: ${JSON.stringify(answerData.result)}\n${mealPlanText}`);
  questionsContainer.insertBefore(card, questionsContainer.firstChild);
};

// Get the form and questions container elements
const form = document.getElementById('question-form');
const questionsContainer = document.getElementById('questions-container');
const spinner = document.getElementById('spinner');

// Load previously asked questions from appropriate storage
const previousQuestions = getStorageData();
previousQuestions.forEach(qa => {
  const card = createCard(`Question: ${qa.question}`, `Answer: ${qa.answer}`);
  questionsContainer.appendChild(card);
});

// Add an event listener to the form submission event
form.addEventListener('submit', (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  spinner.style.display = 'block';

  fetch('', {
      method: 'POST',
      body: formData,
      headers: {
          'X-CSRFToken': form.elements.csrfmiddlewaretoken.value
      }
  })
  .then(response => {
    console.log('Server Response:', response);
    if (!response.ok) {
      throw new Error(response.statusText);
    }
    return response.json();
  })  
  .then(response_data => {
      spinner.style.display = 'none';
      form.elements.question.value = '';

      let mealPlanContent = '';

      if (response_data.suggested_meal_plan) {
          // Handle meal plan separately
          response_data.suggested_meal_plan.forEach(plan => {
              mealPlanContent += `Plan: ${plan.name}, Chef: ${plan.chef}, Start: ${plan.start_date}`;
              const mealPlanCard = createCard(plan, 'meal_plan');
              questionsContainer.appendChild(mealPlanCard);
          });
      }

      previousQuestions.push({
          question: response_data.question,
          answer: response_data.response,
      });

      saveToStorage(previousQuestions);
  })
  .catch(error => {
      spinner.style.display = 'none';
      console.error("Error details: ", error);
      alert("We're experiencing technical difficulties. Please try again later.");
  });
});

document.addEventListener('DOMContentLoaded', (event) => {
  const addMealPlanToCartButton = document.getElementById('addMealPlanToCart');
  if(addMealPlanToCartButton) {
      addMealPlanToCartButton.addEventListener('click', () => {
          // Your logic for adding all meal plans to cart
          addMealPlanToCart(response.suggested_meal_plan.result); // Assuming this is the array of meal plans
      });
  }
});
