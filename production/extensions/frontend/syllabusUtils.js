/**
 * syllabusUtils.js — Shared logic for syllabus-driven AI generation.
 *
 * Extracted from SyllabusNode.svelte so that both:
 *   - SyllabusNode  (Trial / always-unlocked sidebar content)
 *   - LessonCardPanel (paid content, accessed via BreadcrumbBar)
 * share a single implementation of the Smart Router + prompt-build flow.
 *
 * All functions are plain async functions that read Svelte stores via get().
 * This file is a standard ES module — no .svelte compiler step required.
 */

import { get } from 'svelte/store';
import { goto } from '$app/navigation';
import { page } from '$app/stores';
import { showSidebar, mobile, user, chatId } from '$lib/stores';
import { pendingSyllabusTag, studyPanelOpen } from './syllabusStore.js';

// ── Cache key helpers ─────────────────────────────────────────────────────────

/** Normalise any value to a string so null/undefined don't corrupt cache keys. */
export const norm = (v) => (v == null ? '' : String(v));

/**
 * Build a deterministic cache identity string from a tag-data tuple.
 * All eight fields participate so that MCQ variants (different level/number)
 * for the same concept produce distinct cache keys.
 */
export const cacheKey = (t) =>
    [
        norm(t.data_function),
        norm(t.exam),
        norm(t.subject),
        norm(t.topic),
        norm(t.lesson),
        norm(t.concept),
        norm(t.level),
        norm(t.number),
    ].join('||');

// ── Prompt builder ────────────────────────────────────────────────────────────

/**
 * Fetch a prompt template from the backend and substitute {VAR_NAME} placeholders.
 *
 * Resolution order (handled server-side):
 *   1. Per-exam override   — SYLLABUS_DIR/{exam}/prompts/{functionName}.txt
 *   2. Global default      — PROMPTS_DIR/{functionName}.txt
 *   3. Hardcoded fallback  — server returns a minimal "template missing" message
 *
 * @param {string} functionName  e.g. 'ask_agent' or 'mcq_widget'
 * @param {Object} vars          substitution map, e.g. { SUBJECT: '...', TOPIC: '...' }
 * @returns {Promise<string>}    fully substituted prompt text
 */
export async function buildPrompt(functionName, vars) {
    const examParam = vars.EXAM ? `?exam=${encodeURIComponent(vars.EXAM)}` : '';
    try {
        const res = await fetch(`/api/ext/syllabus/prompts/${functionName}${examParam}`);
        if (res.ok) {
            let template = await res.text();
            // value == null ? '' : String(value) preserves falsy-but-meaningful
            // values like 0 or false that a plain `value || ''` would erase.
            for (const [key, value] of Object.entries(vars)) {
                const replacement = value == null ? '' : String(value);
                template = template.replaceAll(`{${key}}`, replacement);
            }
            return template;
        }
    } catch (err) {
        console.error('[syllabusUtils] Failed to fetch prompt template:', err);
    }
    // Minimal in-browser fallback — only reached when the API itself is down.
    return (
        `You are an expert tutor for ${vars.SUBJECT || 'this topic'}.\n` +
        `Topic: ${vars.TOPIC || ''}\n` +
        `Focus: ${vars.CONCEPT || ''}\n` +
        `Generate study material.`
    );
}

// ── Smart Router + generation orchestrator ────────────────────────────────────

/**
 * Core generation flow:
 *   1. Build click identity from linkData + metadata.
 *   2. Check Smart Router cache (server-side /history/lookup, fallback /history/tags).
 *   3. Cache hit  → navigate to existing chat.
 *   4. Cache miss → build prompt, store pendingSyllabusTag, navigate to /?q=...
 *
 * This function is intentionally side-effect-heavy: it writes to the
 * pendingSyllabusTag store, calls goto(), and may close the sidebar.
 * Callers must hold an active Svelte component context for goto() to work.
 *
 * @param {Object} linkData   data-* attributes from the HTML anchor tag
 * @param {Object} metadata   { lesson, concept, clarification } from parse_html_file
 * @param {string} linkLabel  display label of the button that was clicked
 */
export async function generateNotes(linkData, metadata, linkLabel) {
    // Close the Study Materials modal before navigating to the chat.
    studyPanelOpen.set(false);

    const $user     = get(user);
    const $chatId   = get(chatId);
    const $page     = get(page);
    const $mobile   = get(mobile);

    const clickIdentity = {
        data_function: linkData.function,
        exam:          linkData.exam    || 'General',
        subject:       linkData.subject || 'General',
        topic:         linkData.topic   || 'General',
        lesson:        linkData.lesson  || 'General',
        concept:       metadata.concept  || '',
        level:         linkData.level   || '',
        number:        linkData.number  || '',
    };
    const clickKey = cacheKey(clickIdentity);

    // ── 1. Smart Router cache check ───────────────────────────────────────────
    if ($user) {
        let resolvedChatId = null;
        let lookupOk = false;

        try {
            const params = new URLSearchParams({
                data_function: clickIdentity.data_function,
                exam:          clickIdentity.exam,
                subject:       clickIdentity.subject,
                topic:         clickIdentity.topic,
                lesson:        clickIdentity.lesson,
                concept:       clickIdentity.concept,
                level:         clickIdentity.level,
                number:        clickIdentity.number,
            });
            const res = await fetch(`/api/ext/history/lookup?${params.toString()}`);
            if (res.ok) {
                lookupOk = true;
                const data = await res.json();
                resolvedChatId = data?.chat_id || null;
            }
        } catch (err) {
            console.error('[syllabusUtils] Lookup endpoint failed, falling back to /tags', err);
        }

        if (!lookupOk) {
            try {
                const res = await fetch(`/api/ext/history/tags/${$user.id}`);
                if (res.ok) {
                    const data = await res.json();
                    const existing = (data.tags || []).find((t) => cacheKey(t) === clickKey);
                    if (existing) resolvedChatId = existing.chat_id;
                }
            } catch (err) {
                console.error('[syllabusUtils] /tags fallback failed:', err);
            }
        }

        if (resolvedChatId) {
            console.log('[syllabusUtils] Cache hit — navigating to existing chat:', resolvedChatId);
            goto(`/c/${resolvedChatId}`);
            if ($mobile) showSidebar.set(false);
            return;
        }
    }

    // ── 2. Cache miss — arm HistoryTracker and navigate to new chat ───────────
    // Capture origin state AT click time so HistoryTracker can distinguish
    // "the chat I clicked from" from "the freshly created chat".
    const originChatId  = $chatId || '';
    const originPathname = $page?.url?.pathname || '';
    const requestId =
        typeof crypto !== 'undefined' && crypto.randomUUID
            ? crypto.randomUUID()
            : `syl-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

    pendingSyllabusTag.set({
        function:        clickIdentity.data_function,
        exam:            clickIdentity.exam,
        subject:         clickIdentity.subject,
        topic:           clickIdentity.topic,
        lesson:          clickIdentity.lesson,
        concept:         clickIdentity.concept,
        level:           clickIdentity.level,
        number:          clickIdentity.number,
        // Race-guard fields consumed only by HistoryTracker:
        originChatId,
        originPathname,
        requestId,
        createdAt: Date.now(),
    });

    // ── 3. Build prompt and navigate ──────────────────────────────────────────
    const templateVars = {
        EXAM:          linkData.exam    || '',
        SUBJECT:       linkData.subject || 'this topic',
        TOPIC:         linkData.topic   || metadata.lesson || '',
        CONCEPT:       metadata.concept        || '',
        CLARIFICATION: metadata.clarification  || '',
        LINK_LABEL:    linkLabel               || '',
        NUM_QUESTIONS: String(linkData.number  || 5),
        LEVEL:         linkData.level          || 'basic',
    };

    const promptText = await buildPrompt(linkData.function, templateVars);
    goto(`/?q=${encodeURIComponent(promptText)}`);

    if ($mobile) showSidebar.set(false);
}
