document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const openAIChatBtn = document.getElementById('openAIChat');
    const closeAIChatBtn = document.getElementById('closeAIChat');
    const aiAssistantChat = document.getElementById('aiAssistantChat');
    const aiChatMessages = document.getElementById('aiChatMessages');
    const aiMessageInput = document.getElementById('aiMessageInput');
    const sendAIMessageBtn = document.getElementById('sendAIMessage');

    // Conversation ID storage
    let conversationId = localStorage.getItem('aiConversationId');

    // Function to open chat with AI
    function openAIChat() {
        aiAssistantChat.style.display = 'flex';

        // If no conversation ID, create a new one
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
                    loadConversationHistory();
                } else {
                    console.error('Error creating conversation:', data.message);
                }
            })
            .catch(error => {
                console.error('Request error:', error);
            });
        } else {
            // If conversation ID exists, load history
            loadConversationHistory();
        }
    }

    // Load conversation history
    function loadConversationHistory() {
        if (!conversationId) {
            console.error('No conversation ID found');
            return;
        }

        fetch(`/aisha/get_conversation_history/${conversationId}/`)
        .then(response => {
            if (!response.ok) {
                // If conversation not found, create a new one
                localStorage.removeItem('aiConversationId');
                openAIChat();
                return null;
            }
            return response.json();
        })
        .then(data => {
            if (data && data.status === 'success') {
                // Clear message history
                aiChatMessages.innerHTML = '';

                // Add messages from history
                data.messages.forEach(msg => {
                    const messageClass = msg.role === 'user' ? 'user-message' : 'ai-message';
                    addMessageToChat(msg.content, messageClass);
                });

                // Scroll to last message
                aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
            }
        })
        .catch(error => {
            console.error('Error loading history:', error);
            // On error create a new conversation
            localStorage.removeItem('aiConversationId');
            openAIChat();
        });
    }

    // Function to close chat with AI
    function closeAIChat() {
        aiAssistantChat.style.display = 'none';
    }

    // Function to send message
    function sendAIMessage() {
        const message = aiMessageInput.value.trim();
        if (!message || !conversationId) return;

        // Add user message to chat
        addMessageToChat(message, 'user-message');

        // Clear input field
        aiMessageInput.value = '';

        // Show loading indicator
        const loadingMessage = document.createElement('div');
        loadingMessage.className = 'message ai-message';
        loadingMessage.innerHTML = '<div class="message-content">Думаю...</div>';
        loadingMessage.id = 'ai-loading-message';
        aiChatMessages.appendChild(loadingMessage);

        // Scroll to last message
        aiChatMessages.scrollTop = aiChatMessages.scrollHeight;

        // Send message to server
        fetch('/aisha/send_message/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                conversation_id: conversationId,
                message: message
            })
        })
        .then(response => response.json())
        .then(data => {
            // Remove loading indicator
            const loadingMessage = document.getElementById('ai-loading-message');
            if (loadingMessage) {
                loadingMessage.remove();
            }

            if (data.status === 'success') {
                // Add AI response to chat
                addMessageToChat(data.response, 'ai-message');

                // Scroll to last message
                aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
            } else {
                console.error('Error sending message:', data.message);
                addMessageToChat('Извините, произошла ошибка. Пожалуйста, попробуйте еще раз.', 'ai-message');
            }
        })
        .catch(error => {
            console.error('Error sending message:', error);

            // Remove loading indicator
            const loadingMessage = document.getElementById('ai-loading-message');
            if (loadingMessage) {
                loadingMessage.remove();
            }

            addMessageToChat('Извините, произошла ошибка. Пожалуйста, попробуйте еще раз.', 'ai-message');
        });
    }

    // Function to add message to chat
    function addMessageToChat(message, messageClass) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${messageClass}`;
        messageElement.innerHTML = `<div class="message-content">${message}</div>`;
        aiChatMessages.appendChild(messageElement);

        // Scroll to last message
        aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
    }

    // Get CSRF token from cookies
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

    // Events
    if (openAIChatBtn) {
        openAIChatBtn.addEventListener('click', function() {
            console.log("Open AI Chat button clicked");
            openAIChat();
        });
    }

    if (closeAIChatBtn) {
        closeAIChatBtn.addEventListener('click', function() {
            closeAIChat();
        });
    }

    if (sendAIMessageBtn) {
        sendAIMessageBtn.addEventListener('click', function() {
            sendAIMessage();
        });
    }

    if (aiMessageInput) {
        aiMessageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendAIMessage();
            }
        });
    }

    // Handle chat form submission (if form exists)
    const chatForm = document.querySelector('#aiAssistantChat form');
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            sendAIMessage();
        });
    }

    // Random AI hints popup
    function showRandomAIHint() {
        if (aiAssistantChat.style.display === 'none' || aiAssistantChat.style.display === '') {
            const hints = [
                'Привет, нужна помощь?',
                'Посоветовать что-то?',
                'Найти что-нибудь?',
                'Я могу помочь выбрать подарок!',
                'Хотите узнать о новинках?'
            ];

            // Create hint popup
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

            // Add hint to page
            const aiWrapper = document.querySelector('.ai-assistant-wrapper');
            if (aiWrapper) {
                aiWrapper.appendChild(hintElement);

                // On hint click open chat
                hintElement.addEventListener('click', function() {
                    openAIChat();
                    hintElement.remove();
                });

                // Remove hint after 5 seconds
                setTimeout(() => {
                    if (hintElement.parentNode) {
                        hintElement.remove();
                    }
                }, 5000);
            }
        }
    }

    // Show random hint 30-60 seconds after page load
    setTimeout(showRandomAIHint, Math.random() * 30000 + 30000);
});