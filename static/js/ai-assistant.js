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

    // Функция для открытия чата с ИИ
    function openAIChat() {
        aiAssistantChat.style.display = 'flex';

        // Если нет ID диалога, создаем новый
        if (!conversationId) {
            fetch('/aisha/create_conversation/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    conversationId = data.conversation_id;
                    localStorage.setItem('aiConversationId', conversationId);
                    connectWebSocket();
                } else {
                    console.error('Ошибка создания диалога:', data.message);
                }
            })
            .catch(error => {
                console.error('Ошибка запроса:', error);
            });
        } else {
            // Если ID диалога есть, загружаем историю
            fetch(`/aisha/get_conversation_history/${conversationId}/`)
            .then(response => {
                if (!response.ok) {
                    // Если диалог не найден, создаем новый
                    localStorage.removeItem('aiConversationId');
                    openAIChat();
                    return null; // Важно вернуть null, чтобы следующий then не выполнялся
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
                        addMessageToChat(msg.content, messageClass);
                    });

                    // Прокручиваем до последнего сообщения
                    aiChatMessages.scrollTop = aiChatMessages.scrollHeight;

                    // Подключаемся к WebSocket
                    connectWebSocket();
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки истории:', error);
                // При ошибке создаем новый диалог
                localStorage.removeItem('aiConversationId');
                openAIChat();
            });
        }
    }

    // Подключение к WebSocket
    function connectWebSocket() {
        if (conversationId === null) {
            console.error('ID диалога не найден');
            return;
        }

        if (aiSocket) {
            aiSocket.close();
        }

        // Протокол зависит от текущего соединения
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${wsProtocol}${window.location.host}/ws/aisha/${conversationId}/`;

        try {
            aiSocket = new WebSocket(wsUrl);

            aiSocket.onopen = function(e) {
                console.log('WebSocket соединение установлено');
                // Разблокируем кнопку отправки
                sendAIMessageBtn.disabled = false;
            };

            aiSocket.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.status === 'success' && data.results) {
                        data.results.forEach(item => {
                            const link = document.createElement('a');
                            link.href = item.url;
                            link.textContent = item.name;
                            link.target = '_blank';
                            link.className = 'product-link';
                            aiChatMessages.appendChild(link);
                        });
                    } else {
                        addMessageToChat(data.message, 'ai-message');
                    }
                    aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
                } catch (error) {
                    console.error('Ошибка обработки сообщения:', error);
                }
            };

            aiSocket.onclose = function(e) {
                console.log('WebSocket соединение закрыто, код:', e.code, 'причина:', e.reason);
                // Блокируем кнопку отправки
                sendAIMessageBtn.disabled = true;

                // Пытаемся переподключиться через 3 секунды
                setTimeout(function() {
                    if (aiAssistantChat.style.display !== 'none') {
                        connectWebSocket();
                    }
                }, 3000);
            };

            aiSocket.onerror = function(e) {
                console.error('WebSocket ошибка:', e);
                // Блокируем кнопку отправки
                sendAIMessageBtn.disabled = true;
            };
        } catch (error) {
            console.error('Ошибка создания WebSocket:', error);
        }
    }

    // Функция для закрытия чата с ИИ
    function closeAIChat() {
        aiAssistantChat.style.display = 'none';

        // Закрываем WebSocket соединение
        if (aiSocket) {
            aiSocket.close();
            aiSocket = null;
        }
    }

    // Функция для отправки сообщения
function sendAIMessage() {
    const message = aiMessageInput.value.trim();
    if (!message) return;

    if (aiSocket && aiSocket.readyState === WebSocket.OPEN) {
        try {
            // Отображаем сообщение пользователя сразу
            // addMessageToChat(message, 'user-message');
            // Закомментируйте эту строку, так как сообщение будет добавлено после получения от сервера

            // Отправка сообщения через WebSocket
            aiSocket.send(JSON.stringify({
                'message': message
            }));

            // Очищаем поле ввода
            aiMessageInput.value = '';

            // Прокручиваем до последнего сообщения
            aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
        } catch (error) {
            console.error('Ошибка отправки сообщения:', error);
            alert('Не удалось отправить сообщение. Пожалуйста, обновите страницу и попробуйте снова.');
        }
    } else {
        console.error('WebSocket не подключен, состояние:', aiSocket ? aiSocket.readyState : 'null');
        // Пытаемся переподключиться
        connectWebSocket();
        setTimeout(function() {
            if (aiSocket && aiSocket.readyState === WebSocket.OPEN) {
                sendAIMessage();
            } else {
                alert('Не удалось подключиться к серверу. Пожалуйста, обновите страницу и попробуйте снова.');
            }
        }, 1000);
    }
}

    // Функция добавления сообщения в чат
    function addMessageToChat(message, messageClass) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${messageClass}`;
        messageElement.innerHTML = `<div class="message-content">${message}</div>`;
        aiChatMessages.appendChild(messageElement);
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
            if (e.key === 'Enter') {
                sendAIMessage();
            }
        });
    }

    // Добавляем обработчик для формы отправки (если вдруг форма есть)
    const chatForm = document.querySelector('#aiAssistantChat form');
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            sendAIMessage();
        });
    }

    // Периодически проверяем, не завершена ли сессия
    setInterval(function() {
        if (aiAssistantChat.style.display !== 'none' && aiSocket && aiSocket.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
    }, 5000);

    // Случайные всплывающие подсказки от ИИ
    function showRandomAIHint() {
        if (aiAssistantChat.style.display === 'none' || aiAssistantChat.style.display === '') {
            const hints = [
                'Привет, нужна помощь?',
                'Посоветовать что-то?',
                'Найти что-нибудь?',
                'Я могу помочь выбрать подарок!',
                'Хотите узнать о новинках?'
            ];

            // Создаем всплывающую подсказку
            const hintElement = document.createElement('div');
            hintElement.className = 'ai-hint';
            hintElement.innerHTML = hints[Math.floor(Math.random() * hints.length)];
            hintElement.style.position = 'absolute';
            hintElement.style.bottom = '70px';
            hintElement.style.right = '0';
            hintElement.style.backgroundColor = '#fff';
            hintElement.style.padding = '10px 15px';
            hintElement.style.borderRadius = '10px';
            hintElement.style.boxShadow = '0 3px 10px rgba(0, 0, 0, 0.2)';
            hintElement.style.maxWidth = '250px';
            hintElement.style.cursor = 'pointer';

            // Добавляем подсказку на страницу
            const aiWrapper = document.querySelector('.ai-assistant-wrapper');
            if (aiWrapper) {
                aiWrapper.appendChild(hintElement);

                // По клику на подсказку открываем чат
                hintElement.addEventListener('click', function() {
                    openAIChat();
                    hintElement.remove();
                });

                // Удаляем подсказку через 5 секунд
                setTimeout(() => {
                    if (hintElement.parentNode) {
                        hintElement.remove();
                    }
                }, 5000);
            }
        }
    }

    // Показываем случайную подсказку через 30-60 секунд после загрузки страницы
    setTimeout(showRandomAIHint, Math.random() * 30000 + 30000);
});