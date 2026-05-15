define(['jquery', 'block_ai_assistant/api_handler', 'block_ai_assistant/mathjax_loader'], function($, apiHandler, mathjaxLoader) {
    var state = {
        currentPage: 1,
        syllabusData: null,
        config: {}
    };

    var getDom = function() {
        return {
            modal: document.getElementById('ai-assistant-history-modal'),
            closeButton: document.getElementById('ai-assistant-history-close'),
            historyBody: document.getElementById('ai-assistant-history-body'),
            subjectSelect: document.getElementById('history-subject'),
            topicSelect: document.getElementById('history-topic'),
            lessonSelect: document.getElementById('history-lesson'),
            loadButton: document.getElementById('history-load-button'),
            pagination: document.getElementById('ai-assistant-history-pagination')
        };
    };

    var escapeHtml = function(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

    var formatMCQIfNeeded = function(botresponse, functioncalled) {
        var allowedWidgets = ['mcq_widget', 'mcq_widget_basic', 'mcq_widget_intermediate', 'mcq_widget_advanced', 'mcq_agent', 'mcq'];
        if (allowedWidgets.indexOf(functioncalled) === -1) return null;
        
        try {
            var mcqData = typeof botresponse === 'string' ? JSON.parse(botresponse) : botresponse;
            if (!mcqData.questions || !Array.isArray(mcqData.questions)) return null;
            
            var level = (mcqData.metadata && mcqData.metadata.level) ? mcqData.metadata.level : 'Unknown';
            var html = '<div class="mcq-history-formatted"><div class="mcq-history-header">';
            html += '<strong>📚 ' + escapeHtml(level.toUpperCase()) + ' MCQ Practice Set</strong>';
            html += '<span class="mcq-count-badge">' + mcqData.questions.length + ' Questions</span></div>';
            
            mcqData.questions.forEach(function(q, idx) {
                html += '<div class="mcq-history-question">';
                html += '<div class="mcq-q-number">Question ' + (idx + 1) + '</div>';
                html += '<div class="mcq-q-text">' + q.question + '</div>';
                html += '<div class="mcq-q-options">';
                
                q.options.forEach(function(opt, optIdx) {
                    var letter = String.fromCharCode(65 + optIdx);
                    var isCorrect = letter === q.correct;
                    var correctClass = isCorrect ? 'mcq-correct-option' : '';
                    var correctMarker = isCorrect ? '<span class="correct-marker">✓</span>' : '';
                    html += '<div class="mcq-q-option ' + correctClass + '">';
                    html += '<strong>' + letter + ')</strong> ' + opt + correctMarker;
                    html += '</div>';
                });
                
                html += '</div><div class="mcq-q-explanation"><strong>💡 Explanation:</strong> ' + q.explanation + '</div></div>';
            });
            
            html += '<button class="mcq-practice-again-btn" onclick="window.aiAssistantMCQReopen(this)" data-mcq-data=\'' + JSON.stringify(mcqData).replace(/'/g, '&#39;') + '\'>🔄 Practice These Questions Again</button></div>';
            return html;
        } catch (e) {
            console.error('Failed to format MCQ response:', e);
            return null;
        }
    };

    window.aiAssistantMCQReopen = function(button) {
        try {
            var mcqData = JSON.parse(button.getAttribute('data-mcq-data'));
            closeHistoryWidget();
            if (typeof window.openMCQWidgetWithData === 'function') {
                window.openMCQWidgetWithData(mcqData);
            } else {
                alert('MCQ practice widget is not available. Please refresh the page.');
            }
        } catch (e) {
            alert('Failed to load MCQ practice');
        }
    };

    var populateSubjects = function() {
        var dom = getDom();
        if (!state.syllabusData || !Array.isArray(state.syllabusData)) {
            dom.subjectSelect.innerHTML = '<option value="">No subjects available</option>';
            return;
        }
        dom.subjectSelect.innerHTML = '<option value="">-- Select Subject --</option>';
        dom.subjectSelect.innerHTML += '<option value="general">📝 General (Unfiltered Conversations)</option>';
        dom.subjectSelect.innerHTML += '<option disabled>────────────────────</option>';
        state.syllabusData.forEach(function(subject) {
            dom.subjectSelect.innerHTML += '<option value="' + subject.subject_key + '">' + subject.subject + '</option>';
        });
    };

    var bindEvents = function() {
        var dom = getDom();
        
        dom.subjectSelect.addEventListener('change', function() {
            var subjectKey = dom.subjectSelect.value;
            dom.topicSelect.innerHTML = '<option value="">-- Select Topic --</option>';
            dom.lessonSelect.innerHTML = '<option value="">-- Select Lesson --</option>';
            dom.topicSelect.disabled = true;
            dom.lessonSelect.disabled = true;
            dom.loadButton.disabled = false;
            
            if (!subjectKey) return;
            if (subjectKey === 'general') {
                dom.topicSelect.innerHTML = '<option value="">Not applicable</option>';
                dom.lessonSelect.innerHTML = '<option value="">Not applicable</option>';
                dom.loadButton.disabled = false;
                return;
            }
            
            dom.loadButton.disabled = false;
            var subjectData = state.syllabusData.find(function(s) { return s.subject_key === subjectKey; });
            if (subjectData && subjectData.topics) {
                dom.topicSelect.innerHTML += '<option value="">All topics</option>';
                subjectData.topics.forEach(function(topic) {
                    dom.topicSelect.innerHTML += '<option value="' + topic.topic_key + '">' + topic.topic + '</option>';
                });
                dom.topicSelect.disabled = false;
            }
        });

        dom.topicSelect.addEventListener('change', function() {
            var subjectKey = dom.subjectSelect.value;
            var topicKey = dom.topicSelect.value;
            dom.lessonSelect.innerHTML = '<option value="">-- Select Lesson --</option>';
            dom.lessonSelect.disabled = true;
            dom.loadButton.disabled = false;
            
            if (!topicKey) {
                dom.lessonSelect.innerHTML = '<option value="">All lessons</option>';
                return;
            }
            var subjectData = state.syllabusData.find(function(s) { return s.subject_key === subjectKey; });
            var topicData = subjectData ? subjectData.topics.find(function(t) { return t.topic_key === topicKey; }) : null;
            
            if (topicData && topicData.lessons) {
                dom.lessonSelect.innerHTML += '<option value="">All lessons</option>';
                topicData.lessons.forEach(function(lesson) {
                    var lessonText = typeof lesson === 'string' ? lesson : lesson.lesson;
                    dom.lessonSelect.innerHTML += '<option value="' + lessonText + '">' + lessonText + '</option>';
                });
                dom.lessonSelect.disabled = false;
            }
        });

        dom.lessonSelect.addEventListener('change', function() {
            dom.loadButton.disabled = false;
        });

        dom.loadButton.addEventListener('click', function() {
            var subjectKey = dom.subjectSelect.value;
            var topicKey = dom.topicSelect.value;
            var lesson = dom.lessonSelect.value;
            
            state.currentPage = 1; // Reset to first page on new load

            
            if (subjectKey === 'general') {
                fetchHistory('general', '', '');
            } else {
                fetchHistory(subjectKey, topicKey || '', lesson || '');
            }
        });

        dom.closeButton.addEventListener('click', closeHistoryWidget);
        dom.modal.addEventListener('click', function(e) { if (e.target === dom.modal) closeHistoryWidget(); });
        document.addEventListener('keydown', function(e) { if (e.key === 'Escape' && dom.modal.style.display === 'flex') closeHistoryWidget(); });
    };

    var renderHistoryAccordion = function(conversations) {
        var dom = getDom();
        dom.historyBody.innerHTML = '';
        var markdown = window.markdownit ? window.markdownit({html:true,breaks:true}) : null;
        
        conversations.forEach(function(conv, index) {
            var item = document.createElement('div');
            item.className = 'accordion-item';
            var text = conv.usertext.length > 80 ? conv.usertext.substring(0, 80) + '...' : conv.usertext;
            
            var contextInfo = '';
            var parts = [];
            if (conv.subject && conv.subject !== 'general') parts.push(conv.subject);
            if (conv.topic) parts.push(conv.topic);
            if (conv.lesson) parts.push(conv.lesson);
            if (parts.length > 0) contextInfo = '<div style="font-size: 0.85rem; color: #6c757d; margin-top: 4px;">📂 ' + parts.join(' → ') + '</div>';
            
            item.innerHTML = '<div class="accordion-header" data-index="' + index + '"><div style="flex:1;"><strong>' + conv.formattedtime + ':</strong> ' + text + contextInfo + '</div><span style="color: #6c757d; font-size: 1.2rem;">▼</span></div>' +
                             '<div class="accordion-content" style="display: none;">' +
                             '<div class="message user-message"><div class="avatar">U</div><div class="content">' + conv.usertext + '</div></div>' +
                             '<div class="message bot-message"><div class="avatar">A</div><div class="content" data-rendered="false" data-function="' + (conv.functioncalled || '') + '">' + conv.botresponse + '</div></div></div>';
            
            var header = item.querySelector('.accordion-header');
            var content = item.querySelector('.accordion-content');
            var botContent = item.querySelector('.bot-message .content');
            var arrow = header.querySelector('span');
            
            header.addEventListener('click', function() {
                var isVisible = content.style.display === 'block';
                content.style.display = isVisible ? 'none' : 'block';
                arrow.textContent = isVisible ? '▼' : '▲';
                
                if (!isVisible && botContent.dataset.rendered === 'false') {
                    var mcqFormatted = formatMCQIfNeeded(botContent.textContent, botContent.dataset.function);
                    if (mcqFormatted) {
                        botContent.innerHTML = mcqFormatted;
                    }
                    mathjaxLoader.typeset(botContent);
                    botContent.dataset.rendered = 'true';
                }
            });
            dom.historyBody.appendChild(item);
        });
    };

    var renderPagination = function(paginationData, subjectKey, topicKey, lesson) {
        var dom = getDom();
        if (!paginationData || paginationData.totalpages <= 1) {
            dom.pagination.style.display = 'none';
            return;
        }
        
        var html = '<div style="display:flex; justify-content:center; gap:10px; margin-top:15px; align-items:center;">';
        
        if (paginationData.currentpage > 1) {
            html += '<button class="ai-assistant-button-secondary pagination-btn" data-page="' + (paginationData.currentpage - 1) + '" style="padding: 4px 10px; font-size: 0.9rem;">&laquo; Previous</button>';
        }
        
        html += '<span style="font-size:0.9rem; color:#6c757d;">Page ' + paginationData.currentpage + ' of ' + paginationData.totalpages + '</span>';
        
        if (paginationData.currentpage < paginationData.totalpages) {
            html += '<button class="ai-assistant-button-secondary pagination-btn" data-page="' + (paginationData.currentpage + 1) + '" style="padding: 4px 10px; font-size: 0.9rem;">Next &raquo;</button>';
        }
        
        html += '</div>';
        dom.pagination.innerHTML = html;
        dom.pagination.style.display = 'block';
        
        var btns = dom.pagination.querySelectorAll('.pagination-btn');
        for (var i = 0; i < btns.length; i++) {
            btns[i].addEventListener('click', function() {
                state.currentPage = parseInt(this.getAttribute('data-page'));
                fetchHistory(subjectKey, topicKey, lesson);
            });
        }
    };

    var fetchHistory = function(subjectKey, topicKey, lesson) {
        var dom = getDom();
        dom.historyBody.innerHTML = '<div class="loading">⏳ Loading conversations...</div>';
        
        var payload = {
            sesskey: state.config.sesskey,
            courseid: state.config.courseid,
            page: state.currentPage,
            perpage: 20,
            subject: subjectKey === 'general' ? '' : subjectKey,
            topic: subjectKey === 'general' ? '' : topicKey,
            lesson: subjectKey === 'general' ? '' : lesson,
            general: subjectKey === 'general'
        };
        
        apiHandler.callJsonApi(state.config.historyAjaxUrl, payload)
            .then(function(data) {
                if (data.status === 'error') throw new Error(data.message);
                if (data.conversations && data.conversations.length > 0) {
                    renderHistoryAccordion(data.conversations);
                    renderPagination(data.pagination, subjectKey, topicKey, lesson);
                } else {
                    dom.historyBody.innerHTML = '<div class="empty-state"><p>📭 No conversations found.</p></div>';
                    dom.pagination.style.display = 'none';
                }
            })
            .catch(function(err) {
                dom.historyBody.innerHTML = '<div class="error">❌ Failed to load history. Please try again.</div>';
            });
    };

    var loadSyllabus = function() {
        var dom = getDom();
        dom.subjectSelect.innerHTML = '<option value="">Loading subjects...</option>';
        apiHandler.fetchJson(state.config.syllabusAjaxUrl + '?blockid=' + state.config.blockInstanceId + '&sesskey=' + state.config.sesskey)
            .then(function(data) {
                state.syllabusData = data;
                populateSubjects();
            })
            .catch(function() {
                dom.subjectSelect.innerHTML = '<option value="">Failed to load syllabus</option>';
            });
    };

    var openHistoryWidget = function() {
        var dom = getDom();
        dom.modal.style.display = 'flex';
        if (!state.syllabusData) loadSyllabus();
    };

    var closeHistoryWidget = function() {
        var dom = getDom();
        dom.modal.style.display = 'none';
        dom.historyBody.innerHTML = '<div class="empty-state"><p>📚 Select a category above to view your conversation history</p></div>';
        dom.pagination.style.display = 'none';
    };

    var init = function(config) {
        state.config = config;
        bindEvents();
        window.openHistoryWidget = openHistoryWidget;
        window.closeHistoryWidget = closeHistoryWidget;
    };

    return { init: init };
});
