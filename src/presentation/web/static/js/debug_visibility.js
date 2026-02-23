
(function () {
    console.log('🔍 DEBUG: Checking Clients View state...');
    const view = document.getElementById('clients-view');
    const listView = document.getElementById('clients-list-view');
    const tbody = document.getElementById('clients-table-body');
    const mainContent = document.querySelector('.main-content');

    console.log('Clients View Element:', view);
    if (view) {
        console.log('Clients View Styles:', {
            display: view.style.display,
            visibility: window.getComputedStyle(view).visibility,
            opacity: window.getComputedStyle(view).opacity,
            height: view.offsetHeight,
            width: view.offsetWidth,
            classes: view.className
        });
    }

    console.log('Main Content Styles:', {
        display: mainContent ? window.getComputedStyle(mainContent).display : 'N/A',
        height: mainContent ? mainContent.offsetHeight : 0
    });

    console.log('Tbody rows:', tbody ? tbody.rows.length : 'N/A');

    // Check for overlapping views
    const allViews = document.querySelectorAll('.view, .content-view');
    allViews.forEach(v => {
        if (window.getComputedStyle(v).display !== 'none') {
            console.log('Visible view found:', v.id, window.getComputedStyle(v).zIndex);
        }
    });
})();
