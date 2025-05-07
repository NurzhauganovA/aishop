document.addEventListener('DOMContentLoaded', function() {
    // Обработчик для корзины (обновление количества)
    const cartQuantityInputs = document.querySelectorAll('.cart-quantity-input');
    if (cartQuantityInputs) {
        cartQuantityInputs.forEach(input => {
            input.addEventListener('change', function() {
                const itemId = this.dataset.itemId;
                const quantity = parseInt(this.value);
                
                if (quantity < 1) {
                    this.value = 1;
                    return;
                }
                
                updateCartItem(itemId, quantity);
            });
        });
    }
    
    // Функция обновления корзины
    function updateCartItem(itemId, quantity) {
        fetch('/update-cart/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                item_id: itemId,
                quantity: quantity
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Обновляем отображение подытога
                const subtotalElement = document.getElementById(`subtotal-${itemId}`);
                if (subtotalElement) {
                    subtotalElement.textContent = data.subtotal;
                }
                
                // Обновляем общую сумму
                const totalElement = document.getElementById('cart-total');
                if (totalElement) {
                    totalElement.textContent = data.total;
                }
                
                // Обновляем счетчик товаров в корзине
                const cartCountElement = document.querySelector('.cart-count');
                if (cartCountElement) {
                    cartCountElement.textContent = data.item_count;
                }
            } else {
                alert(data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    }
    
    // Получение CSRF-токена из cookies
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
    
    // Обработчик для отслеживания времени просмотра товара
    const productDetailPage = document.querySelector('.product-detail-page');
    if (productDetailPage) {
        const productId = productDetailPage.dataset.productId;
        
        // При закрытии страницы отправляем время просмотра
        window.addEventListener('beforeunload', function() {
            fetch(`/leave-view-time/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });
        });
    }
    
    // Добавление в список желаний
    const wishlistButtons = document.querySelectorAll('.wishlist-button');
    if (wishlistButtons) {
        wishlistButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const productId = this.dataset.productId;
                const isInWishlist = this.dataset.inWishlist === 'true';
                
                fetch('/add-to-wishlist/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: `product_id=${productId}`
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        if (data.added) {
                            this.innerHTML = '<i class="bi bi-heart-fill"></i>';
                            this.dataset.inWishlist = 'true';
                        } else {
                            this.innerHTML = '<i class="bi bi-heart"></i>';
                            this.dataset.inWishlist = 'false';
                        }
                        
                        // Обновляем счетчик товаров в списке желаний
                        const wishlistCountElement = document.querySelector('.wishlist-count');
                        if (wishlistCountElement) {
                            const currentCount = parseInt(wishlistCountElement.textContent || '0');
                            wishlistCountElement.textContent = data.added ? currentCount + 1 : currentCount - 1;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                });
            });
        });
    }
    
    // Обработчик для оценок в форме отзыва
    const ratingStars = document.querySelectorAll('.rating-form .rating .bi');
    if (ratingStars) {
        ratingStars.forEach(star => {
            // При наведении
            star.addEventListener('mouseover', function() {
                const rating = this.dataset.rating;
                
                ratingStars.forEach(s => {
                    if (s.dataset.rating <= rating) {
                        s.classList.remove('bi-star');
                        s.classList.add('bi-star-fill');
                    } else {
                        s.classList.remove('bi-star-fill');
                        s.classList.add('bi-star');
                    }
                });
            });
            
            // При клике
            star.addEventListener('click', function() {
                const rating = this.dataset.rating;
                document.getElementById('rating').value = rating;
            });
        });
        
        // При уходе с области звезд
        const ratingContainer = document.querySelector('.rating-form .rating');
        if (ratingContainer) {
            ratingContainer.addEventListener('mouseleave', function() {
                const currentRating = document.getElementById('rating').value;
                
                ratingStars.forEach(s => {
                    if (s.dataset.rating <= currentRating) {
                        s.classList.remove('bi-star');
                        s.classList.add('bi-star-fill');
                    } else {
                        s.classList.remove('bi-star-fill');
                        s.classList.add('bi-star');
                    }
                });
            });
        }
    }
    
    // Уведомления в реальном времени
    function connectNotificationWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${wsProtocol}${window.location.host}/ws/notifications/`;
        
        const notificationSocket = new WebSocket(wsUrl);
        
        notificationSocket.onopen = function(e) {
            console.log('Соединение с уведомлениями установлено');
        };
        
        notificationSocket.onmessage = function(e) {
            const data = JSON.parse(e.data);
            
            if (data.type === 'notification') {
                showNotification(data.notification);
                updateNotificationCount(data.unread_count);
            } else if (data.type === 'unread_count') {
                updateNotificationCount(data.count);
            }
        };
        
        notificationSocket.onclose = function(e) {
            console.log('Соединение с уведомлениями закрыто');
            
            // Пытаемся переподключиться через 3 секунды
            setTimeout(function() {
                connectNotificationWebSocket();
            }, 3000);
        };
        
        notificationSocket.onerror = function(e) {
            console.error('Ошибка соединения с уведомлениями:', e);
        };
    }
    
    // Если пользователь авторизован, подключаемся к WebSocket
    const userMenu = document.getElementById('navbarDropdown');
    if (userMenu) {
        connectNotificationWebSocket();
    }
    
    // Функция отображения уведомления
    function showNotification(notification) {
        // Создаем элемент уведомления
        const toastElement = document.createElement('div');
        toastElement.className = 'toast';
        toastElement.setAttribute('role', 'alert');
        toastElement.setAttribute('aria-live', 'assertive');
        toastElement.setAttribute('aria-atomic', 'true');
        
        toastElement.innerHTML = `
            <div class="toast-header">
                <strong class="me-auto">${notification.title}</strong>
                <small>${new Date(notification.created_at).toLocaleString()}</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${notification.message}
                ${notification.link ? `<div class="mt-2 pt-2 border-top"><a href="${notification.link}" class="btn btn-sm btn-primary">Перейти</a></div>` : ''}
            </div>
        `;
        
        // Добавляем уведомление на страницу
        if (!document.querySelector('.toast-container')) {
            const toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        
        document.querySelector('.toast-container').appendChild(toastElement);
        
        // Показываем уведомление
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
    }
    
    // Функция обновления счетчика непрочитанных уведомлений
    function updateNotificationCount(count) {
        const notificationBadge = document.querySelector('.notification-badge');
        
        if (notificationBadge) {
            if (count > 0) {
                notificationBadge.textContent = count;
                notificationBadge.style.display = 'inline-block';
            } else {
                notificationBadge.style.display = 'none';
            }
        }
    }
});