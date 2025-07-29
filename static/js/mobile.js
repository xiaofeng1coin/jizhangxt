document.addEventListener('DOMContentLoaded', () => {

    // --- Core: Side Navigation Toggle ---
    const menuToggle = document.querySelector('.menu-toggle');
    const navOverlay = document.querySelector('.nav-overlay');
    if (menuToggle && navOverlay) {
        const toggleNav = () => document.body.classList.toggle('nav-open');
        menuToggle.addEventListener('click', toggleNav);
        navOverlay.addEventListener('click', toggleNav);
    }

    // --- Global: Flash Messages via SweetAlert2 ---
    const flashContainer = document.getElementById('flash-container-mobile');
    if (flashContainer) {
        flashContainer.querySelectorAll('div').forEach(flash => {
            const category = flash.dataset.category || 'info';
            const message = flash.dataset.message;
            let icon = 'info';
            if (category === 'success') icon = 'success';
            if (category === 'danger') icon = 'error';
            if (category === 'warning') icon = 'warning';
            
            Swal.fire({
                toast: true, position: 'top', icon: icon, title: message,
                showConfirmButton: false, timer: 3000, timerProgressBar: true,
                background: '#1e1e1e', color: '#e0e0e0'
            });
        });
    }

    // --- Global: Delete Confirmation ---
    document.querySelectorAll('.delete-form').forEach(form => {
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            Swal.fire({
                title: '确认操作', text: this.dataset.message, icon: 'warning',
                showCancelButton: true, confirmButtonText: '确定删除', cancelButtonText: '取消',
                confirmButtonColor: '#f44336', background: '#1e1e1e', color: '#e0e0e0'
            }).then(result => result.isConfirmed && this.submit());
        });
    });

    // --- Add/Edit Form: Dynamic Category Dropdown ---
    const modernForm = document.querySelector('.modern-form');
    if (modernForm) {
        const typeExpense = document.getElementById('type_expense');
        const typeIncome = document.getElementById('type_income');
        const categorySelect = document.getElementById('category');

        const populateCategories = () => {
            const isExpense = typeExpense.checked;
            const categories = isExpense ? G_EXPENSE_CATEGORIES : G_INCOME_CATEGORIES;
            
            categorySelect.innerHTML = ''; // Clear options
            
            categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat;
                option.textContent = cat;
                if (cat === G_SELECTED_CATEGORY) {
                    option.selected = true;
                }
                categorySelect.appendChild(option);
            });
        };

        typeExpense.addEventListener('change', populateCategories);
        typeIncome.addEventListener('change', populateCategories);
        
        // Initial population
        populateCategories();
    }
});
