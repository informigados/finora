document.addEventListener('DOMContentLoaded', function() {
    var toastElList = [].slice.call(document.querySelectorAll('.toast'))
    var toastList = toastElList.map(function(toastEl) {
        return new bootstrap.Toast(toastEl, {
            autohide: true,
            delay: 5000
        })
    })
    toastList.forEach(toast => toast.show())
});
