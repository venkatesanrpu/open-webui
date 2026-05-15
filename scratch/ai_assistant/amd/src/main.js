define(['jquery', 'block_ai_assistant/api_handler', 'block_ai_assistant/ui_manager', 'block_ai_assistant/mathjax_loader'], function($, apiHandler, ui, mathjax) {
    var config = {};
    
    var lookupHistory = function(userText) {
        if (!config.historyAjaxUrl) return Promise.resolve(null);
        var payload = {
            action: 'lookup',
            sesskey: config.sesskey,
            courseid: config.courseid,
            history: {
                usertext: userText
            }
        };
        return apiHandler.callJsonApi(config.historyAjaxUrl, payload)
            .then(function(data) {
                if (data && data.status === 'success' && data.hit) {
                    return data;
                }
                return null;
            }).catch(function() { return null; });
    };

    var sendMessage = function(detail) {
        var dom = ui.getDomElements();
        var userText = String(detail.agent_text).trim();
        if (!userText) return;
        var functionCalled = detail.function || 'ask_agent';
        
        ui.renderMessage(userText, 'user');
        ui.showTypingIndicator();
        
        lookupHistory(userText)
            .then(function(cachedResult) {
                if (cachedResult && cachedResult.botresponse) {
                    ui.removeTypingIndicator();
                    var contentDiv = ui.renderMessage('', 'bot');
                    var noticeDiv = document.createElement('div');
                    noticeDiv.className = 'ai-assistant-history-notice';
                    noticeDiv.textContent = cachedResult.notice || 'Fetched from history';
                    contentDiv.appendChild(noticeDiv);
                    
                    var responseDiv = document.createElement('div');
                    responseDiv.className = 'ai-assistant-message-response';
                    contentDiv.appendChild(responseDiv);
                    ui.renderBotResponseFinal(responseDiv, cachedResult.botresponse);
                    
                    ui.state.messageHistory.push({
                        usertext: userText,
                        botresponse: cachedResult.botresponse,
                        functioncalled: functionCalled,
                        subject: detail.subject || '',
                        topic: detail.topic || '',
                        lesson: detail.lesson || ''
                    });
                    localStorage.setItem('ai_assistant_history_' + config.courseid, JSON.stringify(ui.state.messageHistory));
                    dom.chatInput.value = '';
                    return;
                }
                
                var payload = new URLSearchParams();
                payload.append('sesskey', config.sesskey);
                payload.append('agent_config_key', config.agentkey);
                payload.append('agent_text', userText);
                payload.append('courseid', config.courseid);
                payload.append('function', functionCalled);
                if (detail.level) payload.append('level', detail.level);
                if (detail.target) payload.append('target', detail.target);
                if (detail.subject) payload.append('subject', detail.subject);
                if (detail.topic) payload.append('topic', detail.topic);
                if (detail.lesson) payload.append('lesson', detail.lesson);
                if (detail.tags) payload.append('tags', Array.isArray(detail.tags) ? detail.tags.join(',') : detail.tags);
                
                return apiHandler.callApi(config.functionUrls[functionCalled] || config.askAgentAjaxUrl, payload)
                    .then(function(data) {
                        ui.removeTypingIndicator();
                        if (data.status !== 'success') throw new Error(data.message || 'Error communicating with AI agent');
                        
                        ui.state.messageHistory.push({
                            usertext: userText,
                            botresponse: data.html,
                            functioncalled: functionCalled,
                            subject: detail.subject || '',
                            topic: detail.topic || '',
                            lesson: detail.lesson || ''
                        });
                        localStorage.setItem('ai_assistant_history_' + config.courseid, JSON.stringify(ui.state.messageHistory));
                        
                        var contentDiv = ui.renderMessage('', 'bot');
                        ui.renderBotResponseFinal(contentDiv, data.html);
                        dom.chatInput.value = '';
                    });
            })
            .catch(function(error) {
                ui.removeTypingIndicator();
                ui.renderMessage('Sorry, an error occurred: ' + error.message, 'bot');
                dom.chatInput.value = '';
            });
    };

    var bindEvents = function() {
        var dom = ui.getDomElements();
        
        dom.triggerButton.addEventListener('click', ui.openChatWindow);
        dom.closeButton.addEventListener('click', ui.closeChatWindow);
        dom.fullscreenButton.addEventListener('click', ui.toggleFullscreen);
        
        if (dom.guidedSearchButton) {
            dom.guidedSearchButton.addEventListener('click', function() {
                var btn = this;
                var originalIcon = btn.innerHTML;
                btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;border-top-color:currentColor;"></div>';
                
                apiHandler.fetchJson(config.syllabusAjaxUrl + '?blockid=' + config.blockInstanceId + '&sesskey=' + config.sesskey)
                    .then(function(data) {
                        btn.innerHTML = originalIcon;
                        if (!Array.isArray(data) || data.length === 0) {
                            alert('Sorry, no guided search/syllabus data is available for this course.');
                            return;
                        }
                        
                        // Populate modal subject dropdown
                        dom.guidedSearchSubject.innerHTML = '<option value="">-- Please select a subject --</option>';
                        data.forEach(function(s) {
                            dom.guidedSearchSubject.innerHTML += '<option value="' + escapeHtml(s.subject_key) + '">' + escapeHtml(s.subject) + '</option>';
                        });
                        
                        // Reset topic and lesson
                        dom.guidedSearchTopic.innerHTML = '<option value="">-- Please select a topic --</option>';
                        dom.guidedSearchTopic.disabled = true;
                        dom.guidedSearchLesson.innerHTML = '<option value="">-- Please select a lesson --</option>';
                        dom.guidedSearchLesson.disabled = true;
                        dom.guidedSearchQuestion.value = '';
                        
                        // Store syllabus data globally for cascading dropdowns
                        ui.state.syllabusData = data;
                        
                        dom.guidedSearchModal.style.display = 'flex';
                    })
                    .catch(function(error) {
                        btn.innerHTML = originalIcon;
                        console.error(error);
                        alert('Sorry, failed to load the guided search topics.');
                    });
            });
        }
        
        if (dom.guidedSearchSubject) {
            dom.guidedSearchSubject.addEventListener('change', function() {
                var subjectKey = this.value;
                dom.guidedSearchTopic.innerHTML = '<option value="">-- Please select a topic --</option>';
                dom.guidedSearchLesson.innerHTML = '<option value="">-- Please select a lesson --</option>';
                dom.guidedSearchTopic.disabled = true;
                dom.guidedSearchLesson.disabled = true;
                
                if (!subjectKey || !ui.state.syllabusData) return;
                
                var subjectData = ui.state.syllabusData.find(function(s) { return s.subject_key === subjectKey; });
                if (subjectData && subjectData.topics) {
                    subjectData.topics.forEach(function(t) {
                        dom.guidedSearchTopic.innerHTML += '<option value="' + escapeHtml(t.topic_key) + '">' + escapeHtml(t.topic) + '</option>';
                    });
                    dom.guidedSearchTopic.disabled = false;
                }
            });
            
            dom.guidedSearchTopic.addEventListener('change', function() {
                var subjectKey = dom.guidedSearchSubject.value;
                var topicKey = this.value;
                dom.guidedSearchLesson.innerHTML = '<option value="">-- Please select a lesson --</option>';
                dom.guidedSearchLesson.disabled = true;
                
                if (!topicKey || !ui.state.syllabusData) return;
                
                var subjectData = ui.state.syllabusData.find(function(s) { return s.subject_key === subjectKey; });
                var topicData = subjectData ? subjectData.topics.find(function(t) { return t.topic_key === topicKey; }) : null;
                
                if (topicData && topicData.lessons) {
                    topicData.lessons.forEach(function(l) {
                        var lText = typeof l === 'string' ? l : l.lesson;
                        dom.guidedSearchLesson.innerHTML += '<option value="' + escapeHtml(lText) + '">' + escapeHtml(lText) + '</option>';
                    });
                    dom.guidedSearchLesson.disabled = false;
                }
            });
            
            dom.guidedSearchCancel.addEventListener('click', function() {
                dom.guidedSearchModal.style.display = 'none';
            });
            
            dom.guidedSearchForm.addEventListener('submit', function(e) {
                e.preventDefault();
                var subject = dom.guidedSearchSubject.value;
                var topic = dom.guidedSearchTopic.value;
                var lesson = dom.guidedSearchLesson.value;
                var question = dom.guidedSearchQuestion.value;
                
                if (!subject || !topic || !lesson || !question) {
                    alert('Please fill all fields');
                    return;
                }
                
                dom.guidedSearchModal.style.display = 'none';
                
                if (!ui.state.isChatVisible) ui.openChatWindow();
                setTimeout(function() {
                    sendMessage({
                        function: 'ask_agent',
                        agent_text: question,
                        subject: subject,
                        topic: topic,
                        lesson: lesson
                    });
                }, ui.state.isChatVisible ? 0 : 300);
            });
        }
        
        dom.historyButton.addEventListener('click', function() {
            if (typeof window.openHistoryWidget === 'function') {
                window.openHistoryWidget();
            } else {
                alert('History widget is not loaded.');
            }
        });
        
        dom.sendButton.addEventListener('click', function() {
            sendMessage({
                function: 'ask_agent',
                agent_text: dom.chatInput.value,
                courseid: config.courseid
            });
        });
        
        dom.chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                dom.sendButton.click();
            }
        });
        
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('notes-link')) {
                e.preventDefault();
                var dataset = e.target.dataset;
                if (!dataset.function || !dataset.agentText) return;
                if (!ui.state.isChatVisible) ui.openChatWindow();
                setTimeout(function() {
                    sendMessage({
                        function: dataset.function,
                        agent_text: dataset.agentText,
                        target: dataset.target || '',
                        subject: dataset.subject || '',
                        topic: dataset.topic || '',
                        lesson: dataset.lesson || '',
                        tags: dataset.tags || ''
                    });
                }, ui.state.isChatVisible ? 0 : 300);
            }
            
            var mcqLink = e.target.closest('.mcq-link, .mcq-flashcard-link');
            if (mcqLink) {
                e.preventDefault();
                var d = mcqLink.dataset;
                if (!d.function || !d.level || !d.agentText) return;
                if (typeof window.openMCQWidget === 'function') {
                    window.openMCQWidget({
                        function: d.function,
                        level: d.level,
                        agent_text: d.agentText,
                        target: d.target || '',
                        subject: d.subject || '',
                        topic: d.topic || '',
                        lesson: d.lesson || '',
                        tags: d.tags || '',
                        number: d.number || 5
                    });
                }
            }
        });
    };

    var escapeHtml = function(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

    var loadHistory = function() {
        var saved = localStorage.getItem('ai_assistant_history_' + config.courseid);
        if (saved) {
            try {
                var history = JSON.parse(saved);
                if (Array.isArray(history) && history.length > 0) {
                    ui.state.messageHistory = history;
                    history.forEach(function(msg) {
                        ui.renderMessage(msg.usertext, 'user');
                        if (msg.botresponse) {
                            var botDiv = ui.renderMessage('', 'bot');
                            ui.renderBotResponseFinal(botDiv, msg.botresponse);
                        }
                    });
                }
            } catch (e) {
                console.error('Failed to parse history:', e);
            }
        }
    };

    var init = function(c) {
        config = c;
        mathjax.init();
        bindEvents();
        loadHistory();
        console.log('AI Assistant main initialized.');
    };

    return { init: init };
});
