document.addEventListener('DOMContentLoaded', function() {
    // Элементы интерфейса
    const openAIChatBtn = document.getElementById('openAIChat');
    const closeAIChatBtn = document.getElementById('closeAIChat');
    const aiAssistantChat = document.getElementById('aiAssistantChat');
    const aiChatMessages = document.getElementById('aiChatMessages');
    const aiMessageInput = document.getElementById('aiMessageInput');
    const sendAIMessageBtn = document.getElementById('sendAIMessage');

    // WebSocket соединение
    let aiSocket = null;
    let conversationId = localStorage.getItem('aiConversationId');
    let isConnecting = false;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;

    // Функция для отображения статуса соединения
    function updateConnectionStatus(status, message) {
        const statusElement = document.getElementById('aiConnectionStatus');
        if (!statusElement) {
            const newStatusElement = document.createElement('div');
            newStatusElement.id = 'aiConnectionStatus';
            newStatusElement.className = 'connection-status';
            const chatHeader = aiAssistantChat.querySelector('.chat-header');
            if (chatHeader) {
                chatHeader.appendChild(newStatusElement);
            }
        }

        const statusEl = document.getElementById('aiConnectionStatus');
        if (statusEl) {
            statusEl.className = `connection-status ${status}`;
            statusEl.textContent = message || '';

            if (status === 'connected') {
                setTimeout(() => {
                    statusEl.style.display = 'none';
                }, 2000);
            } else {
                statusEl.style.display = 'block';
            }
        }
    }

    // Функция для открытия чата с ИИ
    function openAIChat() {
        aiAssistantChat.style.display = 'flex';
        aiMessageInput.focus();

        // Если нет ID диалога, создаем новый
        if (!conversationId) {
            createNewConversation();
        } else {
            // Если ID диалога есть, загружаем историю
            loadConversationHistory();
        }
    }

    // Создание нового диалога
    function createNewConversation() {
        updateConnectionStatus('connecting', 'Создание нового диалога...');

        fetch('/aisha/create_conversation/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                conversationId = data.conversation_id;
                localStorage.setItem('aiConversationId', conversationId);
                console.log('Новый диалог создан с ID:', conversationId);
                connectWebSocket();
            } else {
                throw new Error(data.message || 'Неизвестная ошибка при создании диалога');
            }
        })
        .catch(error => {
            console.error('Ошибка создания диалога:', error);
            updateConnectionStatus('error', 'Ошибка создания диалога');
            addSystemMessage(`Ошибка создания диалога: ${error.message}`);
        });
    }

    // Загрузка истории диалога
    function loadConversationHistory() {
        updateConnectionStatus('connecting', 'Загрузка истории...');

        fetch(`/aisha/get_conversation_history/${conversationId}/`)
        .then(response => {
            if (!response.ok) {
                if (response.status === 404) {
                    // Диалог не найден, создаем новый
                    localStorage.removeItem('aiConversationId');
                    conversationId = null;
                    createNewConversation();
                    return null;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data && data.status === 'success') {
                // Очищаем историю сообщений
                aiChatMessages.innerHTML = '';

                // Добавляем сообщения из истории
                data.messages.forEach(msg => {
                    const messageClass = msg.role === 'user' ? 'user-message' : 'ai-message';
                    addMessageToChat(msg.content, messageClass, false);
                });

                // Прокручиваем до последнего сообщения
                scrollToBottom();

                // Подключаемся к WebSocket
                connectWebSocket();
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки истории:', error);
            updateConnectionStatus('error', 'Ошибка загрузки истории');
            // При ошибке создаем новый диалог
            localStorage.removeItem('aiConversationId');
            conversationId = null;
            createNewConversation();
        });
    }

    // Подключение к WebSocket
    function connectWebSocket() {
        if (!conversationId) {
            console.error('ID диалога не найден');
            updateConnectionStatus('error', 'ID диалога не найден');
            return;
        }

        if (isConnecting) {
            console.log('Уже идет подключение к WebSocket');
            return;
        }

        isConnecting = true;
        updateConnectionStatus('connecting', 'Подключение...');

        // Закрываем существующее соединение
        if (aiSocket) {
            aiSocket.close();
            aiSocket = null;
        }

        // Протокол зависит от текущего соединения
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${wsProtocol}${window.location.host}/ws/aisha/${conversationId}/`;

        console.log('Подключение к WebSocket:', wsUrl);

        try {
            aiSocket = new WebSocket(wsUrl);

            // Таймаут для подключения
            const connectionTimeout = setTimeout(() => {
                if (aiSocket && aiSocket.readyState === WebSocket.CONNECTING) {
                    console.log('Таймаут подключения WebSocket');
                    aiSocket.close();
                    handleConnectionError('Таймаут подключения');
                }
            }, 10000); // 10 секунд

            aiSocket.onopen = function(e) {
                clearTimeout(connectionTimeout);
                isConnecting = false;
                reconnectAttempts = 0;
                console.log('WebSocket соединение установлено');
                updateConnectionStatus('connected', 'Подключено');

                // Разблокируем кнопку отправки
                if (sendAIMessageBtn) {
                    sendAIMessageBtn.disabled = false;
                }

                // Добавляем приветственное сообщение если чат пустой
                if (aiChatMessages.children.length === 0) {
                    addMessageToChat('Привет! Я AISha, ваш персональный помощник. Чем могу помочь?', 'ai-message');
                }
            };

            aiSocket.onmessage = function(event) {
                console.log('Получено сообщение от WebSocket:', event.data);

                try {
                    const data = JSON.parse(event.data);

                    if (data.status === 'error') {
                        addSystemMessage(`Ошибка: ${data.message}`);
                        return;
                    }

                    // ИСПРАВЛЕНИЕ: Игнорируем сообщения от пользователя, так как они уже добавлены в чат
                    if (data.role === 'user') {
                        return;
                    }

                    if (data.status === 'success' && data.results) {
                        // Обработка результатов поиска
                        handleSearchResults(data.results);
                    } else if (data.message !== undefined) {
                        // Обычное сообщение
                        const messageClass = data.role === 'user' ? 'user-message' : 'ai-message';
                        addMessageToChat(data.message, messageClass);
                    }

                } catch (error) {
                    console.error('Ошибка обработки сообщения:', error);
                    addSystemMessage('Ошибка обработки ответа от сервера');
                }
            };

            aiSocket.onclose = function(e) {
                clearTimeout(connectionTimeout);
                isConnecting = false;
                console.log('WebSocket соединение закрыто, код:', e.code, 'причина:', e.reason);

                // Блокируем кнопку отправки
                if (sendAIMessageBtn) {
                    sendAIMessageBtn.disabled = true;
                }

                // Если соединение закрыто не пользователем
                if (e.code !== 1000 && aiAssistantChat.style.display !== 'none') {
                    handleConnectionError('Соединение потеряно');
                }
            };

            aiSocket.onerror = function(e) {
                clearTimeout(connectionTimeout);
                isConnecting = false;
                console.error('WebSocket ошибка:', e);
                handleConnectionError('Ошибка соединения');
            };

        } catch (error) {
            isConnecting = false;
            console.error('Ошибка создания WebSocket:', error);
            handleConnectionError(`Ошибка создания соединения: ${error.message}`);
        }
    }

    // Обработка ошибок соединения и переподключение
    function handleConnectionError(errorMessage) {
        updateConnectionStatus('error', errorMessage);

        if (reconnectAttempts < maxReconnectAttempts && aiAssistantChat.style.display !== 'none') {
            reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000); // Экспоненциальная задержка

            console.log(`Попытка переподключения ${reconnectAttempts}/${maxReconnectAttempts} через ${delay}ms`);
            updateConnectionStatus('connecting', `Переподключение через ${Math.ceil(delay/1000)}с...`);

            setTimeout(() => {
                if (aiAssistantChat.style.display !== 'none') {
                    connectWebSocket();
                }
            }, delay);
        } else {
            updateConnectionStatus('error', 'Не удалось подключиться. Обновите страницу.');
            addSystemMessage('Не удалось подключиться к серверу. Пожалуйста, обновите страницу.');
        }
    }

    // Обработка результатов поиска
    function handleSearchResults(results) {
        addMessageToChat('Вот что я нашла по вашему запросу:', 'ai-message');

        if (results && results.length > 0) {
            const resultsContainer = document.createElement('div');
            resultsContainer.className = 'search-results-container';

            results.forEach(item => {
                const productCard = createProductCard(item);
                resultsContainer.appendChild(productCard);
            });

            const messageElement = document.createElement('div');
            messageElement.className = 'message ai-message';
            messageElement.appendChild(resultsContainer);
            aiChatMessages.appendChild(messageElement);
        } else {
            addMessageToChat('К сожалению, товары по вашему запросу не найдены.', 'ai-message');
        }

        scrollToBottom();
    }

    // Создание карточки товара
    function createProductCard(product) {
        const card = document.createElement('div');
        card.className = 'product-card';

        card.innerHTML = `
            <div class="product-info">
                ${product.image ? 
                    `<img src="${product.image}" alt="${product.name}" class="product-image">` : 
                    '<div class="product-placeholder">📦</div>'
                }
                <div class="product-details">
                    <h6 class="product-name">${product.name}</h6>
                    <div class="product-price">${product.price} ₸</div>
                    ${product.old_price ? 
                        `<div class="product-old-price">${product.old_price} ₸</div>` : 
                        ''
                    }
                    <a href="${product.url}" class="product-link" target="_blank">Посмотреть</a>
                </div>
            </div>
        `;

        return card;
    }

    // Функция для закрытия чата с ИИ
    function closeAIChat() {
        aiAssistantChat.style.display = 'none';

        // Закрываем WebSocket соединение
        if (aiSocket) {
            aiSocket.close(1000, 'Chat closed by user');
            aiSocket = null;
        }

        // Сбрасываем счетчики
        isConnecting = false;
        reconnectAttempts = 0;
    }

    // Функция для отправки сообщения
    function sendAIMessage() {
        const message = aiMessageInput.value.trim();
        if (!message) return;

        // Проверяем состояние WebSocket
        if (!aiSocket || aiSocket.readyState !== WebSocket.OPEN) {
            addSystemMessage('Соединение не установлено. Попытка переподключения...');
            connectWebSocket();

            // Сохраняем сообщение для отправки после подключения
            setTimeout(() => {
                if (aiSocket && aiSocket.readyState === WebSocket.OPEN) {
                    sendMessageToSocket(message);
                } else {
                    addSystemMessage('Не удалось подключиться. Попробуйте позже.');
                }
            }, 2000);
            return;
        }

        sendMessageToSocket(message);
    }

    // Отправка сообщения через WebSocket
    function sendMessageToSocket(message) {
        try {
            // Отображаем сообщение пользователя
            addMessageToChat(message, 'user-message');

            // Отправка сообщения через WebSocket
            aiSocket.send(JSON.stringify({
                'message': message
            }));

            // Очищаем поле ввода
            aiMessageInput.value = '';

            console.log('Сообщение отправлено:', message);

        } catch (error) {
            console.error('Ошибка отправки сообщения:', error);
            addSystemMessage('Ошибка отправки сообщения. Попробуйте еще раз.');
        }
    }

    // Функция добавления сообщения в чат
    function addMessageToChat(message, messageClass, scroll = true) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${messageClass}`;

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = formatMessage(message);

        const messageTime = document.createElement('div');
        messageTime.className = 'message-time';
        messageTime.textContent = new Date().toLocaleTimeString('ru', {
            hour: '2-digit',
            minute: '2-digit'
        });

        messageElement.appendChild(messageContent);
        messageElement.appendChild(messageTime);
        aiChatMessages.appendChild(messageElement);

        if (scroll) {
            scrollToBottom();
        }
    }

    // Добавление системного сообщения
    function addSystemMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message system-message';
        messageElement.innerHTML = `<div class="message-content">${message}</div>`;
        aiChatMessages.appendChild(messageElement);
        scrollToBottom();
    }

    // Форматирование сообщения
    function formatMessage(message) {
        return message
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }

    // Прокрутка до конца
    function scrollToBottom() {
        setTimeout(() => {
            aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
        }, 100);
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

    // События
    if (openAIChatBtn) {
        openAIChatBtn.addEventListener('click', openAIChat);
    }

    if (closeAIChatBtn) {
        closeAIChatBtn.addEventListener('click', closeAIChat);
    }

    if (sendAIMessageBtn) {
        sendAIMessageBtn.addEventListener('click', sendAIMessage);
    }

    if (aiMessageInput) {
        aiMessageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendAIMessage();
            }
        });
    }

    // Закрытие чата при клике вне его области
    document.addEventListener('click', function(e) {
        if (aiAssistantChat &&
            aiAssistantChat.style.display !== 'none' &&
            !aiAssistantChat.contains(e.target) &&
            !openAIChatBtn.contains(e.target)) {
            closeAIChat();
        }
    });

    // Предотвращение закрытия при клике внутри чата
    if (aiAssistantChat) {
        aiAssistantChat.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }

    // Проверка работоспособности WebSocket каждые 30 секунд
    setInterval(function() {
        if (aiAssistantChat &&
            aiAssistantChat.style.display !== 'none' &&
            aiSocket &&
            aiSocket.readyState !== WebSocket.OPEN &&
            !isConnecting) {
            console.log('WebSocket не подключен, попытка переподключения...');
            connectWebSocket();
        }
    }, 30000);

    // Случайные всплывающие подсказки от ИИ
    function showRandomAIHint() {
        if (!aiAssistantChat || aiAssistantChat.style.display === 'none' || aiAssistantChat.style.display === '') {
            const hints = [
                'Привет! Нужна помощь с выбором?',
                'Могу посоветовать что-то интересное!',
                'Ищете что-то конкретное?',
                'Помогу найти идеальный подарок!',
                'Хотите узнать о новинках?'
            ];

            const hintElement = document.createElement('div');
            hintElement.className = 'ai-hint';
            hintElement.innerHTML = hints[Math.floor(Math.random() * hints.length)];

            const aiWrapper = document.querySelector('.ai-assistant-wrapper');
            if (aiWrapper) {
                aiWrapper.appendChild(hintElement);

                hintElement.addEventListener('click', function() {
                    openAIChat();
                    hintElement.remove();
                });

                setTimeout(() => {
                    if (hintElement.parentNode) {
                        hintElement.remove();
                    }
                }, 5000);
            }
        }
    }

    // Показываем случайную подсказку через 30-60 секунд после загрузки страницы
    if (openAIChatBtn) {
        setTimeout(showRandomAIHint, Math.random() * 30000 + 30000);
    }
});