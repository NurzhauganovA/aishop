document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const openAIChatBtn = document.getElementById('openAIChat');
    const closeAIChatBtn = document.getElementById('closeAIChat');
    const aiAssistantChat = document.getElementById('aiAssistantChat');
    const aiChatMessages = document.getElementById('aiChatMessages');
    const aiMessageInput = document.getElementById('aiMessageInput');
    const sendAIMessageBtn = document.getElementById('sendAIMessage');

    // WebSocket connection
    let aiSocket = null;
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
                    connectWebSocket();
                } else {
                    console.error('Error creating conversation:', data.message);
                }
            })
            .catch(error => {
                console.error('Request error:', error);
            });
        } else {
            // If conversation ID exists, load history
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

                    // Connect to WebSocket
                    connectWebSocket();
                }
            })
            .catch(error => {
                console.error('Error loading history:', error);
                // On error create a new conversation
                localStorage.removeItem('aiConversationId');
                openAIChat();
            });
        }
    }

    // Connect to WebSocket
    function connectWebSocket() {
        if (conversationId === null) {
            console.error('Conversation ID not found');
            return;
        }

        if (aiSocket) {
            aiSocket.close();
        }

        // Protocol depends on current connection
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${wsProtocol}${window.location.host}/ws/aisha/${conversationId}/`;

        console.log("Attempting to connect to WebSocket at:", wsUrl);

        try {
            aiSocket = new WebSocket(wsUrl);

            aiSocket.onopen = function(e) {
                console.log('WebSocket connection established');
                // Enable send button
                sendAIMessageBtn.disabled = false;
            };

            aiSocket.onmessage = function(e) {
                console.log("WebSocket message received:", e.data);
                try {
                    const data = JSON.parse(e.data);
                    const messageClass = data.role === 'user' ? 'user-message' : 'ai-message';
                    addMessageToChat(data.message, messageClass);

                    // Scroll to last message
                    aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
                } catch (error) {
                    console.error('Error processing message:', error);
                }
            };

            aiSocket.onclose = function(e) {
                console.log('WebSocket connection closed, code:', e.code, 'reason:', e.reason);
                // Disable send button
                sendAIMessageBtn.disabled = true;

                // Try to reconnect after 3 seconds
                setTimeout(function() {
                    if (aiAssistantChat.style.display !== 'none') {
                        connectWebSocket();
                    }
                }, 3000);
            };

            aiSocket.onerror = function(e) {
                console.error('WebSocket error:', e);
                // Disable send button
                sendAIMessageBtn.disabled = true;
            };
        } catch (error) {
            console.error('Error creating WebSocket:', error);
        }
    }

    // Function to close chat with AI
    function closeAIChat() {
        aiAssistantChat.style.display = 'none';

        // Close WebSocket connection
        if (aiSocket) {
            aiSocket.close();
            aiSocket = null;
        }
    }

    // Function to send message
    function sendAIMessage() {
        const message = aiMessageInput.value.trim();
        if (!message) return;

        if (aiSocket && aiSocket.readyState === WebSocket.OPEN) {
            try {
                // Send message through WebSocket
                aiSocket.send(JSON.stringify({
                    'message': message
                }));

                // Clear input field
                aiMessageInput.value = '';

                // Scroll to last message
                aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
            } catch (error) {
                console.error('Error sending message:', error);
                alert('Failed to send message. Please refresh the page and try again.');
            }
        } else {
            console.error('WebSocket not connected, state:', aiSocket ? aiSocket.readyState : 'null');
            // Try to reconnect
            connectWebSocket();
            setTimeout(function() {
                if (aiSocket && aiSocket.readyState === WebSocket.OPEN) {
                    sendAIMessage();
                } else {
                    alert('Failed to connect to server. Please refresh the page and try again.');
                }
            }, 1000);
        }
    }

    // Function to add message to chat
    function addMessageToChat(message, messageClass) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${messageClass}`;
        messageElement.innerHTML = `<div class="message-content">${message}</div>`;
        aiChatMessages.appendChild(messageElement);
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

    // Periodically check if session has ended
    setInterval(function() {
        if (aiAssistantChat.style.display !== 'none' && aiSocket && aiSocket.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
    }, 5000);

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