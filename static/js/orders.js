let currentUpdatingOrderId = null;
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

// Function to populate the active orders table
function populateActiveOrdersTable(orders) {
    const tbody = document.getElementById('active-orders-tbody');
    tbody.innerHTML = ''; // Clear existing rows
  
    orders.forEach(order => {
        const row = document.createElement('tr');
        row.setAttribute('data-status', order.status);  // Set data-status attribute to the entire row

        // Populate general information cells
        ['id', 'order_date', 'customer__username', 'special_requests'].forEach(field => {
            const cell = document.createElement('td');
            cell.textContent = order[field];
            row.appendChild(cell);
        });
  
        // Add a dropdown for status update
        const statusCell = document.createElement('td');
        const statusDropdown = document.createElement('select');
        statusDropdown.className = 'status-dropdown';
        statusDropdown.dataset.orderId = order.id;

        ['Placed', 'In Progress', 'Completed', 'Cancelled', 'Refunded', 'Delayed'].forEach(status => {
            const option = document.createElement('option');
            option.value = status;
            option.textContent = status;
            if (status === order.status) {
                option.selected = true;
            }
            statusDropdown.appendChild(option);
        });

        // Set the data-status attribute for the statusCell (td)
        statusCell.setAttribute('data-status', order.status); 
        statusCell.appendChild(statusDropdown);
        row.appendChild(statusCell);

        // Add a dummy "Action" button or other actions if needed
        // const actionCell = document.createElement('td');
        // actionCell.textContent = 'N/A'; // or add a real button here
        // row.appendChild(actionCell);
  
        tbody.appendChild(row);
    });
}

// Function to update order status; you'd call your Django API here
function updateOrderStatus(event) {
    const dropdown = event.target;
    const orderId = dropdown.dataset.orderId;
    const newStatus = dropdown.value;
  
    $.ajax({
        url: `/chef_admin/api/update_order_status/${orderId}/`,
        type: 'POST',
        headers: {'X-CSRFToken': csrftoken},
        data: {'new_status': newStatus},
        success: function(response) {
          alert('Status updated successfully.');
          // Update the row's data-status attribute
          const row = document.querySelector(`.status-dropdown[data-order-id="${orderId}"]`).closest('tr');
          row.setAttribute('data-status', newStatus);
          fetchAllOrders(); // Re-fetch the active orders
        },        
        error: function(error) {
            alert('Error updating status: ', error);
        }
    });
}

// Fetch all orders
function fetchAllOrders() {
  $.ajax({
      url: '/chef_admin/api/all_orders/',  // Update the URL here
      type: 'GET',
      headers: {'X-CSRFToken': csrftoken},
      success: function(response) {
          populateActiveOrdersTable(response);
      },
      error: function(error) {
          console.log("Error fetching orders: ", error);
      }
  });
}


// Function to filter rows by status
function filterOrdersByStatus() {
  const filterStatus = document.getElementById('filter-status').value;
  const rows = document.querySelectorAll('#active-orders-tbody tr');

  rows.forEach(row => {
    const rowStatus = row.getAttribute('data-status');
    if (filterStatus === 'all' || rowStatus === filterStatus) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

// Fetch all orders on page load
$(document).ready(function() {
  fetchAllOrders();  // Update the function name here
  
  // Attach event listener for the status dropdowns
  $(document).on('change', '.status-dropdown', updateOrderStatus);
  
  // Attach event listener for the filter dropdown
  document.getElementById('filter-status').addEventListener('change', filterOrdersByStatus);
  });
  