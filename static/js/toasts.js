document.addEventListener('DOMContentLoaded', () => {
    if (typeof bootstrap === 'undefined' || !bootstrap.Toast) {
        return;
    }

    const toastElements = Array.from(document.querySelectorAll('.toast'));
    const toasts = toastElements.map(
        (toastElement) =>
            new bootstrap.Toast(toastElement, {
                autohide: true,
                delay: 5000,
            }),
    );

    toasts.forEach((toast) => toast.show());
});
