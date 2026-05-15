define(['jquery'], function($) {
    var init = function() {
        // We now rely exclusively on Moodle's native filter_mathjaxloader.
        // No custom scripts are injected here to prevent collisions.
    };

    var typeset = function(element) {
        if (typeof window.MathJax !== 'undefined' && window.MathJax.typesetPromise) {
            // Moodle 3.x/4.x MathJax might not have startup promise, but Moodle 5.x (MathJax 3) does.
            if (window.MathJax.startup && window.MathJax.startup.promise) {
                return window.MathJax.startup.promise.then(function() {
                    return window.MathJax.typesetPromise([element]);
                }).catch(function(err) {
                    console.error('MathJax typeset error:', err);
                });
            } else {
                return window.MathJax.typesetPromise([element]).catch(function(err) {
                    console.error('MathJax typeset error:', err);
                });
            }
        } else {
            // Fallback warning if Moodle native MathJax is not loaded/enabled
            if (element && !element.querySelector('.mathjax-fallback-warning')) {
                var warning = document.createElement('div');
                warning.className = 'mathjax-fallback-warning';
                warning.style.cssText = 'font-size: 0.8rem; color: #856404; background-color: #fff3cd; padding: 5px; border-radius: 3px; margin-top: 10px; text-align: center;';
                warning.textContent = '⚠️ Moodle MathJax filter is disabled. Equations may not render correctly.';
                element.appendChild(warning);
            }
            return Promise.resolve();
        }
    };

    return {
        init: init,
        typeset: typeset
    };
});
