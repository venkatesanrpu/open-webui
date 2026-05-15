<script>
    import { onDestroy } from 'svelte';
    import { page } from '$app/stores';
    import { chatId, user } from '$lib/stores';
    import { pendingSyllabusTag } from './syllabusStore.js';

    // Track the last chat ID we tagged to prevent duplicate tagging
    let lastTaggedChatId = '';

    // Stale-tag watchdog state.
    //
    // The pending tag is normally consumed by the reactive block below as soon as
    // Open WebUI persists the new chat (chatId flips from '' to a real id while
    // the user is still on the new-chat page, '/'). If the user cancels or
    // navigates away before that happens, the tag would otherwise sit in the
    // store and be applied to the next unrelated chat. We guard against that in
    // two ways:
    //   1. Route guard: while a pending tag exists AND chatId is still empty
    //      (i.e. the syllabus chat has not been persisted yet), any pathname
    //      that is not '/' means the user has navigated away — clear the tag.
    //   2. Timeout: if neither persistence nor a route change happens within
    //      STALE_TAG_TIMEOUT_MS (5 minutes — comfortably longer than a long
    //      LLM generation, but short enough to prevent cross-session leakage),
    //      clear the tag.
    const STALE_TAG_TIMEOUT_MS = 5 * 60 * 1000;
    let staleTimer = null;

    function clearStaleTimer() {
        if (staleTimer) {
            clearTimeout(staleTimer);
            staleTimer = null;
        }
    }

    function armStaleTimer() {
        clearStaleTimer();
        staleTimer = setTimeout(() => {
            // Only clear if still pending and still unconsumed.
            pendingSyllabusTag.update((v) => {
                if (v) {
                    console.log('[Ext] Pending syllabus tag expired (timeout), clearing.');
                }
                return null;
            });
            staleTimer = null;
        }, STALE_TAG_TIMEOUT_MS);
    }

    // (Re)arm the timer whenever a new pending tag appears; cancel it when the
    // tag is cleared (either by successful tagging or by the route guard).
    $: if ($pendingSyllabusTag) {
        armStaleTimer();
    } else {
        clearStaleTimer();
    }

    // Successful path: chatId becomes a real id => tag it, then clear.
    // This must run BEFORE the route guard below to avoid a race when the
    // route also changes to /c/<id> at the same tick.
    $: if ($chatId && $chatId !== lastTaggedChatId && $pendingSyllabusTag && $user) {
        lastTaggedChatId = $chatId;
        tagChat($chatId, $user.id, $pendingSyllabusTag);
        pendingSyllabusTag.set(null);
    }

    // Route guard: if the user navigates away from the new-chat page ('/')
    // BEFORE a chat id is assigned, the pending tag is stale. Clearing it
    // here prevents the next unrelated chat from being tagged.
    //
    // We deliberately only act when chatId is still empty. Once chatId is set,
    // either the successful path above has already consumed the tag, or the
    // user navigated mid-tag and the duplicate-tagging guard (lastTaggedChatId)
    // handles the rest.
    $: if (
        $pendingSyllabusTag &&
        !$chatId &&
        $page &&
        $page.url &&
        $page.url.pathname !== '/'
    ) {
        console.log('[Ext] Pending syllabus tag abandoned (route changed to', $page.url.pathname, '), clearing.');
        pendingSyllabusTag.set(null);
    }

    onDestroy(clearStaleTimer);

    async function tagChat(cid, userId, tagData) {
        try {
            console.log('[Ext] Tagging chat:', cid, tagData);
            const res = await fetch('/api/ext/history/tag', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chat_id: cid,
                    user_id: userId,
                    data_function: tagData.function || 'unknown',
                    exam: tagData.exam || 'General',
                    subject: tagData.subject || 'General',
                    topic: tagData.topic || 'General',
                    lesson: tagData.lesson || 'General',
                    concept: tagData.concept || 'General',
                    level: tagData.level || '',
                    number: tagData.number != null ? String(tagData.number) : ''
                })
            });

            if (res.ok) {
                console.log(`[Ext] Tagged chat ${cid} successfully.`);
            } else {
                const err = await res.text();
                console.error('[Ext] Tag rejected:', err);
            }
        } catch (e) {
            console.error('[Ext] Tag API unreachable:', e);
        }
    }
</script>
<!-- Headless tracker — renders nothing -->