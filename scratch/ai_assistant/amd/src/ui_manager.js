define(['jquery', 'block_ai_assistant/mathjax_loader'], function($, mathjaxLoader) {
    var state = {
        isChatVisible: false,
        isFullscreen: false,
        messageHistory: [],
        syllabusData: null
    };

    var getDomElements = function() {
        return {
            triggerButton: document.getElementById('ai-assistant-trigger-button'),
            widgetContainer: document.getElementById('ai-assistant-widget-container'),
            chatBody: document.getElementById('ai-assistant-chat-body'),
            chatInput: document.getElementById('ai-assistant-input'),
            sendButton: document.getElementById('ai-assistant-send-button'),
            closeButton: document.getElementById('ai-assistant-close-button'),
            fullscreenButton: document.getElementById('ai-assistant-fullscreen-button'),
            guidedSearchButton: document.getElementById('ai-assistant-guided-search-button'),
            historyButton: document.getElementById('ai-assistant-history-button'),
            guidedSearchModal: document.getElementById('ai-assistant-modal-container'),
            guidedSearchForm: document.getElementById('ai-assistant-modal-form'),
            guidedSearchSubject: document.getElementById('ai-assistant-modal-subject'),
            guidedSearchTopic: document.getElementById('ai-assistant-modal-topic'),
            guidedSearchLesson: document.getElementById('ai-assistant-modal-lesson'),
            guidedSearchCancel: document.getElementById('ai-assistant-modal-cancel'),
            guidedSearchSubmit: document.getElementById('ai-assistant-modal-submit'),
            guidedSearchQuestion: document.getElementById('ai-assistant-modal-question')
        };
    };

    var renderMessage = function(text, from) {
        var dom = getDomElements();
        var messageDiv = document.createElement('div');
        messageDiv.className = 'ai-assistant-message from-' + from;

        var avatar = document.createElement('div');
        avatar.className = 'ai-assistant-avatar';
        avatar.textContent = from === 'user' ? 'U' : 'A';

        var contentDiv = document.createElement('div');
        contentDiv.className = 'ai-assistant-message-content';
        contentDiv.textContent = String(text || '');

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        dom.chatBody.appendChild(messageDiv);
        dom.chatBody.scrollTop = dom.chatBody.scrollHeight;
        return contentDiv;
    };

    var renderBotResponseFinal = function(container, html) {
        if (!container) return;
        container.innerHTML = String(html || '');
        mathjaxLoader.typeset(container);
    };

    var showTypingIndicator = function() {
        var dom = getDomElements();
        if (document.getElementById('ai-assistant-typing-indicator')) return;
        var indicator = document.createElement('div');
        indicator.id = 'ai-assistant-typing-indicator';
        indicator.className = 'ai-assistant-typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        dom.chatBody.appendChild(indicator);
        dom.chatBody.scrollTop = dom.chatBody.scrollHeight;
    };

    var removeTypingIndicator = function() {
        var indicator = document.getElementById('ai-assistant-typing-indicator');
        if (indicator) indicator.remove();
    };

    var openChatWindow = function() {
        var dom = getDomElements();
        state.isChatVisible = true;
        dom.widgetContainer.style.display = 'flex';
        dom.triggerButton.style.display = 'none';
        dom.chatInput.focus();
    };

    var closeChatWindow = function() {
        var dom = getDomElements();
        state.isChatVisible = false;
        dom.widgetContainer.style.display = 'none';
        dom.triggerButton.style.display = 'flex';
    };

    var toggleFullscreen = function() {
        var dom = getDomElements();
        state.isFullscreen = !state.isFullscreen;
        if (state.isFullscreen) {
            dom.widgetContainer.classList.add('fullscreen');
        } else {
            dom.widgetContainer.classList.remove('fullscreen');
        }
    };

    return {
        state: state,
        getDomElements: getDomElements,
        renderMessage: renderMessage,
        renderBotResponseFinal: renderBotResponseFinal,
        showTypingIndicator: showTypingIndicator,
        removeTypingIndicator: removeTypingIndicator,
        openChatWindow: openChatWindow,
        closeChatWindow: closeChatWindow,
        toggleFullscreen: toggleFullscreen
    };
});
