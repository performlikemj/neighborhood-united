// Your JS
let mostPopularDishesChart, salesOverTimeChart, activeOrdersChart, incompleteOrdersChart;

function formatDate(date) {
    const d = new Date(date),
          month = '' + (d.getMonth() + 1),
          day = '' + d.getDate(),
          year = d.getFullYear();

    return [year, month.padStart(2, '0'), day.padStart(2, '0')].join('-');
}

function updateWeekDisplay() {
    const formattedStartDate = formatDate(startDate);
    const formattedEndDate = formatDate(endDate);
    document.getElementById('current-week').textContent = `Week: ${formattedStartDate} to ${formattedEndDate}`;
}


// // Function to update the Most Popular Dishes Chart
function updateMostPopularDishesChart(response) {
    if (mostPopularDishesChart) {
        mostPopularDishesChart.destroy();
    }
    
    let labels = [];
    let data = [];
    for (let i = 0; i < response.length; i++) {
        labels.push(response[i].name);
        data.push(response[i].count);
    }
    
    const ctx = document.getElementById('mostPopularDishesChart').getContext('2d');
    mostPopularDishesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Most Popular Dishes',
                data: data,
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}



function updateSalesOverTimeChart(response) {
    if (salesOverTimeChart) {
        salesOverTimeChart.destroy();
    }
    let labels = [];
    let data = [];
    for (let i = 0; i < response.length; i++) {
        labels.push(response[i].week);
        data.push(response[i].sales);
    }

    const ctx2 = document.getElementById('salesOverTimeChart').getContext('2d');
    salesOverTimeChart = new Chart(ctx2, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Weekly Sales',
                data: data,
                borderColor: 'rgba(255, 99, 132, 1)',
                fill: false
            }]
        }
    });
}

function updateActiveOrdersChart(response) {
    if (activeOrdersChart) {
        activeOrdersChart.destroy();
    }

    let statusCounts = {};
    response.forEach(order => {
        statusCounts[order.status] = (statusCounts[order.status] || 0) + 1;
    });

    const labels = Object.keys(statusCounts);
    const data = Object.values(statusCounts);

    const ctx3 = document.getElementById('activeOrdersChart').getContext('2d');
    activeOrdersChart = new Chart(ctx3, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: ['rgba(255, 99, 132, 0.5)', 'rgba(75, 192, 192, 0.5)']
            }]
        }
    });
}

function updateIncompleteOrdersChart(response) {
    if (incompleteOrdersChart) {
        incompleteOrdersChart.destroy();
    }

    let statusCounts = {};
    response.forEach(order => {
        statusCounts[order.status] = (statusCounts[order.status] || 0) + 1;
    });

    const labels = Object.keys(statusCounts);
    const data = Object.values(statusCounts);

    const ctx4 = document.getElementById('incompleteOrdersChart').getContext('2d');
    incompleteOrdersChart = new Chart(ctx4, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: ['rgba(255, 99, 132, 0.5)', 'rgba(75, 192, 192, 0.5)', 'rgba(255, 206, 86, 0.5)']
            }]
        }
    });
}


// Function to fetch data based on the week
function fetchData(apiUrl, updateFunction) {
    console.log("Fetching data for week starting:", startDate, " and ending:", endDate);
    $.ajax({
        url: `${apiUrl}?start_date=${startDate.toISOString().split('T')[0]}&end_date=${endDate.toISOString().split('T')[0]}`,
        type: 'GET',
        success: function(response) {
            updateFunction(response);
        },
        error: function(error) {
            console.log("Error fetching data: ", error);
        }
    });
    updateWeekDisplay();
}

// Initialize with the current date
let startDate = new Date();
let endDate = new Date();
endDate.setDate(startDate.getDate() + 6);

$(document).ready(function() {
    updateWeekDisplay();
    // Initialize with fetchData
    fetchData('/chef_admin/api/most_popular_dishes/', updateMostPopularDishesChart);
    fetchData('/chef_admin/api/sales_over_time/', updateSalesOverTimeChart);
    fetchData('/chef_admin/api/active_orders/', updateActiveOrdersChart);
    fetchData('/chef_admin/api/incomplete_orders/', updateIncompleteOrdersChart);

    // Add event listeners for the week navigation buttons
    $('#prev-week').click(function() {
        startDate.setDate(startDate.getDate() - 7);
        endDate.setDate(endDate.getDate() - 7);
        // fetchData('/chef_admin/api/most_popular_dishes/', updateMostPopularDishesChart);
        fetchData('/chef_admin/api/sales_over_time/', updateSalesOverTimeChart);
        fetchData('/chef_admin/api/active_orders/', updateActiveOrdersChart);
        fetchData('/chef_admin/api/incomplete_orders/', updateIncompleteOrdersChart);
        updateWeekDisplay();
    });
    
    $('#next-week').click(function() {
        startDate.setDate(startDate.getDate() + 7);
        endDate.setDate(endDate.getDate() + 7);
        fetchData('/chef_admin/api/most_popular_dishes/', updateMostPopularDishesChart);
        fetchData('/chef_admin/api/sales_over_time/', updateSalesOverTimeChart);
        fetchData('/chef_admin/api/active_orders/', updateActiveOrdersChart);
        fetchData('/chef_admin/api/incomplete_orders/', updateIncompleteOrdersChart);
        updateWeekDisplay();
    });
    
});

