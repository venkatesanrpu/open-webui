<?php
namespace block_ai_assistant\local;
defined('MOODLE_INTERNAL') || die();
require_once(__DIR__ . '/Parsedown.php');

class render_helper {

    private const SAFE_TAGS =
        '<p><br><strong><b><em><i><u><s><del><ins>' .
        '<h1><h2><h3><h4><h5><h6>' .
        '<ul><ol><li><dl><dt><dd>' .
        '<blockquote><pre><code><kbd><samp><var>' .
        '<table><thead><tbody><tfoot><tr><th><td><caption>' .
        '<a><img><hr><sup><sub><mark><abbr><span><div>' .
        '<details><summary>';

    /**
     * Convert raw LLM text to safe HTML.
     * Math delimiters \(...\) \[...\] $$...$$ are protected before
     * Parsedown runs so backslashes survive intact for MathJax 3.
     */
    public static function render(string $raw): string {
        if (trim($raw) === '') {
            return '';
        }

        // Strip <think>...</think> blocks (reasoning models).
        $raw = preg_replace('/<think>[\s\S]*?<\/think>/is', '', $raw);

        // Protect math delimiters BEFORE Parsedown touches them.
        $placeholders = [];
        $counter = 0;
        $raw = self::extract_math($raw, $placeholders, $counter);

        // Parse Markdown.
        $pd = new \Parsedown();
        $pd->setSafeMode(false);
        $html = $pd->text($raw);

        // Restore math placeholders verbatim.
        if (!empty($placeholders)) {
            $html = str_replace(
                array_keys($placeholders),
                array_values($placeholders),
                $html
            );
        }

        // Sanitise — strip_tags preserves backslashes unlike HTMLPurifier.
        $html = strip_tags($html, self::SAFE_TAGS);

        // Remove event handlers and javascript: hrefs.
        $html = preg_replace(
            '/\s+on\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]*)/i',
            '',
            $html
        );
        $html = preg_replace(
            '/\s+(href|src)\s*=\s*["\']?\s*(javascript|data)\s*:/i',
            ' $1="#"',
            $html
        );

        return $html;
    }

    /**
     * Extract math spans into placeholders so Parsedown cannot mangle them.
     * Supports: \[...\]  \(...\)  $$...$$
     * Single $...$ intentionally excluded — too ambiguous in general text.
     */
    private static function extract_math(
        string $text,
        array &$placeholders,
        int &$counter
    ): string {
        $store = static function (string $match) use (&$placeholders, &$counter): string {
            $key = '%%AIMATH_' . $counter . '%%';
            $placeholders[$key] = $match;
            $counter++;
            return $key;
        };

        // Display math: \[...\]
        $text = preg_replace_callback(
            '/\\\\\[[\s\S]+?\\\\\]/s',
            fn($m) => $store($m[0]),
            $text
        );

        // Display math: $$...$$
        $text = preg_replace_callback(
            '/\$\$[\s\S]+?\$\$/s',
            fn($m) => $store($m[0]),
            $text
        );

        // Inline math: \(...\)
        $text = preg_replace_callback(
            '/\\\\\([\s\S]+?\\\\\)/s',
            fn($m) => $store($m[0]),
            $text
        );

        return $text;
    }
}
