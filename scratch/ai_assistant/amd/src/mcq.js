define(['jquery', 'block_ai_assistant/api_handler', 'block_ai_assistant/mathjax_loader'], function($, apiHandler, mathjaxLoader) {
    var state = {
        mcqData: null,
        currentCardIndex: 0,
        showingAnswer: false,
        isLoadingMcq: false,
        selectedAnswers: {},
        checkedAnswers: {},
        config: {}
    };

    var getDom = function() {
        return {
            modal: document.getElementById('ai-assistant-mcq-modal'),
            closeButton: document.getElementById('ai-assistant-mcq-close'),
            titleElement: document.getElementById('ai-assistant-mcq-title'),
            cardElement: document.getElementById('ai-assistant-mcq-card'),
            questionView: document.getElementById('mcq-question-view'),
            answerView: document.getElementById('mcq-answer-view'),
            toggleButton: document.getElementById('mcq-toggle-button'),
            prevButton: document.getElementById('mcq-prev-button'),
            nextButton: document.getElementById('mcq-next-button'),
            loadingElement: document.getElementById('mcq-loading'),
            checkButton: document.getElementById('mcq-check-button')
        };
    };

    var escapeHtml = function(text) {
        var div = document.createElement('div');
        div.textContent = String(text || '');
        return div.innerHTML;
    };

    var ensureFeedbackEl = function() {
        var dom = getDom();
        var optionsEl = dom.questionView.querySelector('.mcq-options');
        if (!optionsEl) {
 return null;
}
        var feedbackEl = dom.questionView.querySelector('.mcq-feedback');
        if (!feedbackEl) {
            feedbackEl = document.createElement('div');
            feedbackEl.className = 'mcq-feedback';
            feedbackEl.setAttribute('aria-live', 'polite');
            optionsEl.insertAdjacentElement('afterend', feedbackEl);
        }
        return feedbackEl;
    };

    var ensureCheckButton = function() {
        var dom = getDom();
        var btn = document.getElementById('mcq-check-button');
        if (btn) {
 return btn;
}
        btn = document.createElement('button');
        btn.id = 'mcq-check-button';
        btn.type = 'button';
        btn.className = 'mcq-check-button';
        btn.textContent = 'Check Answer';
        btn.disabled = true;
        if (dom.toggleButton && dom.toggleButton.parentNode) {
            dom.toggleButton.parentNode.insertBefore(btn, dom.toggleButton);
        } else {
            dom.cardElement.appendChild(btn);
        }
        return btn;
    };

    var injectStylesOnce = function() {
        if (document.getElementById('ai-assistant-mcq-test-styles')) {
 return;
}
        var style = document.createElement('style');
        style.id = 'ai-assistant-mcq-test-styles';
        style.textContent = ".mcq-option { padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 8px; margin: 10px 0; }\n" +
            ".mcq-option-label { display: flex; gap: 10px; align-items: flex-start; cursor: pointer; }\n" +
            ".mcq-option-input { margin-top: 4px; }\n" +
            ".mcq-option.is-correct { border-color: #2f855a; background: #f0fff4; }\n" +
            ".mcq-option.is-wrong { border-color: #c53030; background: #fff5f5; }\n" +
            ".mcq-feedback { margin-top: 10px; font-weight: 600; }\n" +
            ".mcq-feedback.is-correct { color: #2f855a; }\n" +
            ".mcq-feedback.is-wrong { color: #c53030; }";
        document.head.appendChild(style);
    };

    var clearFeedbackAndStyling = function() {
        var fb = ensureFeedbackEl();
        if (fb) {
            fb.textContent = '';
            fb.classList.remove('is-correct', 'is-wrong');
        }
        var optionsEl = getDom().questionView.querySelector('.mcq-options');
        if (optionsEl) {
            optionsEl.querySelectorAll('.mcq-option').forEach(function(el) {
 el.classList.remove('is-correct', 'is-wrong');
});
        }
    };

    var applyCheckStyling = function(index) {
        var fb = ensureFeedbackEl();
        var optionsEl = getDom().questionView.querySelector('.mcq-options');
        if (!fb || !optionsEl) {
 return;
}
        optionsEl.querySelectorAll('.mcq-option').forEach(function(el) {
 el.classList.remove('is-correct', 'is-wrong');
});
        fb.classList.remove('is-correct', 'is-wrong');
        var checked = state.checkedAnswers[index];
        if (!checked) {
 return;
}
        var selectedInput = optionsEl.querySelector('input[value="' + checked.selected + '"]');
        var selectedWrapper = selectedInput ? selectedInput.closest('.mcq-option') : null;
        if (checked.isCorrect) {
            fb.textContent = 'Correct.';
            fb.classList.add('is-correct');
            if (selectedWrapper) {
 selectedWrapper.classList.add('is-correct');
}
        } else {
            fb.textContent = 'Incorrect.';
            fb.classList.add('is-wrong');
            if (selectedWrapper) {
 selectedWrapper.classList.add('is-wrong');
}
        }
    };

    var checkCurrentAnswer = function() {
        if (!state.mcqData || !state.mcqData.questions[state.currentCardIndex]) {
 return;
}
        if (state.showingAnswer) {
 return;
}
        var selected = state.selectedAnswers[state.currentCardIndex];
        var fb = ensureFeedbackEl();
        if (!selected) {
            if (fb) {
                fb.textContent = 'Select an option to check.';
                fb.classList.remove('is-correct');
                fb.classList.add('is-wrong');
            }
            return;
        }
        var card = state.mcqData.questions[state.currentCardIndex];
        var isCorrect = (selected === card.correct);
        state.checkedAnswers[state.currentCardIndex] = {selected: selected, isCorrect: isCorrect};
        applyCheckStyling(state.currentCardIndex);
    };

    var renderCard = function(index) {
        var dom = getDom();
        if (!state.mcqData || !state.mcqData.questions || index >= state.mcqData.questions.length) {
 return;
}
        var card = state.mcqData.questions[index];
        var totalCards = state.mcqData.questions.length;
        dom.titleElement.textContent = 'Question ' + (index + 1) + '/' + totalCards;
        var questionTextEl = dom.questionView.querySelector('.mcq-question-text');
        var optionsEl = dom.questionView.querySelector('.mcq-options');
        questionTextEl.innerHTML = '<p><strong>' + card.question + '</strong></p>';
        clearFeedbackAndStyling();
        optionsEl.innerHTML = '';
        var groupName = 'mcq-option-' + index;

        if (!card._shuffledOptions) {
            var originalCorrectIndex = card.correct.charCodeAt(0) - 65;
            var correctTextString = card.options[originalCorrectIndex];

            var shuffledOptions = card.options.slice();
            for (var i = shuffledOptions.length - 1; i > 0; i--) {
                var j = Math.floor(Math.random() * (i + 1));
                var temp = shuffledOptions[i];
                shuffledOptions[i] = shuffledOptions[j];
                shuffledOptions[j] = temp;
            }
            card.options = shuffledOptions;

            var newCorrectIndex = card.options.indexOf(correctTextString);
            card.correct = String.fromCharCode(65 + newCorrectIndex);
            card._shuffledOptions = true;
        }

        card.options.forEach(function(option, i) {
            var optionLetter = String.fromCharCode(65 + i);
            var optionId = groupName + '-' + optionLetter;
            var optionWrapper = document.createElement('div');
            optionWrapper.className = 'mcq-option';
            optionWrapper.innerHTML = '<label class="mcq-option-label" for="' + optionId + '"><input type="radio" id="' + optionId + '" name="' + groupName + '" value="' + optionLetter + '" class="mcq-option-input" /> <span class="mcq-option-text"><strong>' + optionLetter + ')</strong> ' + option + '</span></label>';
            optionsEl.appendChild(optionWrapper);
            var input = optionWrapper.querySelector('input');
            if (state.selectedAnswers[index] === optionLetter) {
 input.checked = true;
}
            input.addEventListener('change', function() {
                state.selectedAnswers[index] = optionLetter;
                delete state.checkedAnswers[index];
                clearFeedbackAndStyling();
                if (dom.checkButton) {
 dom.checkButton.disabled = false;
}
            });
        });

        var correctAnswerEl = dom.answerView.querySelector('.mcq-correct-answer');
        var explanationEl = dom.answerView.querySelector('.mcq-explanation');
        if (correctAnswerEl && explanationEl) {
            var correctIndex = card.correct.charCodeAt(0) - 65;
            var correctText = card.options[correctIndex] || '';
            correctAnswerEl.innerHTML = '<div class="correct-badge">✓ Correct Answer: ' + escapeHtml(card.correct) + '</div><p><strong>' + escapeHtml(card.correct) + ')</strong> ' + correctText + '</p>';
            explanationEl.innerHTML = '<div class="explanation-label">💡 Explanation</div><div>' + card.explanation + '</div>';
        }

        state.showingAnswer = false;
        dom.questionView.style.display = 'block';
        dom.answerView.style.display = 'none';
        dom.toggleButton.textContent = 'Show Answer';
        dom.prevButton.disabled = (index === 0);
        dom.nextButton.disabled = (index === totalCards - 1);
        if (dom.checkButton) {
 dom.checkButton.disabled = !state.selectedAnswers[index];
}
        applyCheckStyling(index);
        mathjaxLoader.typeset(dom.cardElement);
        dom.cardElement.style.opacity = '0';
        setTimeout(function() {
 dom.cardElement.style.opacity = '1';
}, 50);
    };

    var toggleView = function() {
        var dom = getDom();
        state.showingAnswer = !state.showingAnswer;
        if (state.showingAnswer) {
            dom.questionView.style.display = 'none';
            dom.answerView.style.display = 'block';
            dom.toggleButton.textContent = 'Show Question';
            if (dom.checkButton) {
 dom.checkButton.disabled = true;
}
        } else {
            dom.questionView.style.display = 'block';
            dom.answerView.style.display = 'none';
            dom.toggleButton.textContent = 'Show Answer';
            if (dom.checkButton) {
 dom.checkButton.disabled = !state.selectedAnswers[state.currentCardIndex];
}
            applyCheckStyling(state.currentCardIndex);
        }
    };

    var navigateCard = function(direction) {
        if (!state.mcqData || !state.mcqData.questions) {
 return;
}
        var newIndex = state.currentCardIndex + direction;
        if (newIndex >= 0 && newIndex < state.mcqData.questions.length) {
            state.currentCardIndex = newIndex;
            renderCard(state.currentCardIndex);
        }
    };

    var fetchMCQData = function(params) {
        var dom = getDom();
        dom.loadingElement.style.display = 'flex';
        dom.cardElement.style.display = 'none';

        var url = new URL(state.config.mcqWidgetAjaxUrl, window.location.origin);
        url.searchParams.append('sesskey', state.config.sesskey);
        url.searchParams.append('agent_config_key', state.config.agentKey);
        url.searchParams.append('agent_text', params.agent_text);
        url.searchParams.append('level', params.level);
        url.searchParams.append('mainsubject', state.config.mainSubjectKey);
        url.searchParams.append('courseid', state.config.courseid);
        url.searchParams.append('number', params.number || 5);
        if (params.target) {
 url.searchParams.append('target', params.target);
}
        if (params.subject) {
 url.searchParams.append('subject', params.subject);
}
        if (params.topic) {
 url.searchParams.append('topic', params.topic);
}
        if (params.lesson) {
 url.searchParams.append('lesson', params.lesson);
}
        if (params.tags) {
 url.searchParams.append('tags', params.tags);
}

        apiHandler.fetchJson(url.toString())
            .then(function(result) {
                if (result.status !== 'success' || !result.data) {
 throw new Error(result.message || 'Failed to generate MCQs');
}
                state.selectedAnswers = {};
                state.checkedAnswers = {};
                clearFeedbackAndStyling();
                if (dom.checkButton) {
 dom.checkButton.disabled = true;
}
                state.mcqData = result.data;
                if (state.mcqData && state.mcqData.questions) {
                    state.mcqData.questions.sort(function() {
 return Math.random() - 0.5;
});
                }
                state.currentCardIndex = 0;
                dom.loadingElement.style.display = 'none';
                dom.cardElement.style.display = 'block';
                renderCard(0);
            })
            .catch(function(error) {
                dom.loadingElement.innerHTML = '<div class="error-message"><p style="color: #e53e3e; font-weight: 600;">❌ Failed to generate MCQs</p><p>' + escapeHtml(error.message) + '</p><button onclick="window.closeMCQWidget()" style="margin-top: 16px; padding: 10px 24px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer;">Close</button></div>';
            });
    };

    var openMCQWidget = function(params) {
        if (state.isLoadingMcq) {
 return;
}
        state.isLoadingMcq = true;
        var dom = getDom();
        dom.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        fetchMCQData(params);
        state.isLoadingMcq = false;
    };

    var closeMCQWidget = function() {
        var dom = getDom();
        dom.modal.style.display = 'none';
        document.body.style.overflow = '';
        state.mcqData = null;
        state.currentCardIndex = 0;
        state.showingAnswer = false;
        state.isLoadingMcq = false;
        state.selectedAnswers = {};
        state.checkedAnswers = {};
        clearFeedbackAndStyling();
        if (dom.checkButton) {
 dom.checkButton.disabled = true;
}
        dom.loadingElement.innerHTML = '<div class="spinner"></div><p>Generating MCQs...</p>';
        dom.loadingElement.style.display = 'none';
        dom.cardElement.style.display = 'block';
    };

    var openMCQWidgetWithData = function(mcqDataFromHistory) {
        if (!mcqDataFromHistory || !mcqDataFromHistory.questions || mcqDataFromHistory.questions.length === 0) {
            alert('Invalid MCQ data.');
            return;
        }
        var dom = getDom();
        state.mcqData = mcqDataFromHistory;
        if (state.mcqData && state.mcqData.questions) {
            state.mcqData.questions.sort(function() {
 return Math.random() - 0.5;
});
        }
        state.currentCardIndex = 0;
        state.showingAnswer = false;
        state.selectedAnswers = {};
        state.checkedAnswers = {};
        clearFeedbackAndStyling();
        if (dom.checkButton) {
 dom.checkButton.disabled = true;
}
        dom.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        dom.loadingElement.style.display = 'none';
        dom.cardElement.style.display = 'block';
        renderCard(0);
    };

    var init = function(config) {
        state.config = config;
        ensureCheckButton();
        var dom = getDom();
        injectStylesOnce();

        dom.closeButton.addEventListener('click', closeMCQWidget);
        dom.toggleButton.addEventListener('click', toggleView);
        dom.prevButton.addEventListener('click', function() {
 navigateCard(-1);
});
        dom.nextButton.addEventListener('click', function() {
 navigateCard(1);
});
        if (dom.checkButton) {
 dom.checkButton.addEventListener('click', checkCurrentAnswer);
}

        document.addEventListener('keydown', function(e) {
            if (dom.modal.style.display !== 'flex') {
 return;
}
            switch (e.key) {
                case 'ArrowLeft': if (!dom.prevButton.disabled) {
 navigateCard(-1);
} break;
                case 'ArrowRight': if (!dom.nextButton.disabled) {
 navigateCard(1);
} break;
                case ' ':
                case 'Enter': if (e.target.tagName !== 'BUTTON') {
 e.preventDefault(); toggleView();
} break;
                case 'Escape': closeMCQWidget(); break;
            }
        });

        window.openMCQWidget = openMCQWidget;
        window.closeMCQWidget = closeMCQWidget;
        window.openMCQWidgetWithData = openMCQWidgetWithData;
    };

    return {init: init};
});
