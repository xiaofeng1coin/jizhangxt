// static/js/mobile.js
document.addEventListener('DOMContentLoaded', () => {
    // --- Add Record Overlay Logic ---
    const addRecordBtn = document.getElementById('add-record-btn');
    const closeFormBtn = document.getElementById('close-add-form');
    const overlay = document.getElementById('add-record-overlay');
    const form = document.getElementById('add-record-form-mobile');

    if (addRecordBtn && overlay && closeFormBtn) {
        addRecordBtn.addEventListener('click', () => {
            overlay.style.display = 'flex';
        });

        closeFormBtn.addEventListener('click', () => {
            overlay.style.display = 'none';
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.style.display = 'none';
            }
        });
    }

    // --- Add Record Form Logic ---
    if (form) {
        const typeTabs = form.querySelector('.type-tabs');
        const expenseCategories = form.querySelector('#expense-categories');
        const incomeCategories = form.querySelector('#income-categories');
        const recordTypeInput = form.querySelector('#record-type');
        const selectedCategoryInput = form.querySelector('#selected-category');

        typeTabs.addEventListener('click', (e) => {
            if (e.target.matches('.tab-btn')) {
                const type = e.target.dataset.type;

                // Update tabs
                typeTabs.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
                e.target.classList.add('active');

                // Update category visibility
                if (type === 'expense') {
                    expenseCategories.style.display = 'grid';
                    incomeCategories.style.display = 'none';
                } else {
                    expenseCategories.style.display = 'none';
                    incomeCategories.style.display = 'grid';
                }

                // Reset selected category
                selectedCategoryInput.value = '';
                form.querySelectorAll('.category-btn').forEach(btn => btn.classList.remove('selected'));
                recordTypeInput.value = type;
            }
        });

        form.querySelector('.type-category-selector').addEventListener('click', (e) => {
             if (e.target.matches('.category-btn')) {
                const category = e.target.dataset.category;
                selectedCategoryInput.value = category;

                // Update visual selection
                form.querySelectorAll('.category-btn').forEach(btn => btn.classList.remove('selected'));
                e.target.classList.add('selected');
             }
        });
    }

    // --- Generic Delete Confirmation ---
    document.body.addEventListener('submit', function(event) {
        const form = event.target.closest('form.delete-form');
        if (!form) return;

        event.preventDefault();
        const message = form.dataset.message || '确定要删除吗?';

        Swal.fire({
            title: message,
            text: "此操作无法撤销",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#6c757d',
            confirmButtonText: '是的, 删除!',
            cancelButtonText: '取消'
        }).then((result) => {
            if (result.isConfirmed) {
                form.submit();
            }
        });
    });
});
