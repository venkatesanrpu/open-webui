<script>
    import { onDestroy } from 'svelte';
    import { page } from '$app/stores';
    import { chatId, user } from '$lib/stores';
    import { pendingSyllabusTag } from './syllabusStore.js';

    // Track the last chat ID we tagged to prevent duplicate tagging
    let lastTaggedChatId = '';

    // "Armed" gate for the success path.
    //
    // The legitimate Open WebUI new-chat flow always passes through the
    // canonical empty state: $chatId === '' AND pathname === '/' (the
    // /?q=... new-chat page). Only after we observe that state for the
    // CURRENT pending tag do we trust a subsequent non-empty $chatId as the
    // freshly created chat. Without this, a user click on an unrelated
    // sidebar chat (/c/<other>) between pendingSyllabusTag.set(...) and
    // new-chat persistence would land $chatId on <other> — satisfying the
    // origin-chat guard (since <other> !== originChatId) and incorrectly
    // tagging that unrelated chat.
    //
    // Per-tag scope is enforced by `armedRequestId`: arming is keyed to the
    // pending tag's requestId, so a fresh pending tag from a later click
    // resets arming, and a tag that was abandoned/replaced cannot leave
    // residual arming behind for the next click.
    let armedForNewChat = false;
    let armedRequestId = null;

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
    //      STALE_TAG_TIMEOUT_MS (5 minutes default — comfortably longer than a
    //      long LLM generation, but short enough to prevent cross-session
    //      leakage), clear the tag.
    //
    // The timeout can be overridden at build time via the Vite public env
    // variable `VITE_EXT_STALE_TAG_TIMEOUT_MS` (read at module init). Operators
    // who don't set it get the 5-minute default — no Docker/compose change
    // required.
    const DEFAULT_STALE_TAG_TIMEOUT_MS = 5 * 60 * 1000;
    function resolveStaleTagTimeoutMs() {
        try {
            const raw = import.meta?.env?.VITE_EXT_STALE_TAG_TIMEOUT_MS;
            if (raw != null && raw !== '') {
                const parsed = Number(raw);
                if (Number.isFinite(parsed) && parsed > 0) {
                    return parsed;
                }
            }
        } catch (_) {
            // import.meta.env is not always present in test/SSR contexts.
        }
        return DEFAULT_STALE_TAG_TIMEOUT_MS;
    }
    export const STALE_TAG_TIMEOUT_MS = resolveStaleTagTimeoutMs();
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

    // (Re)arm the stale timer + reset the new-chat arming whenever the
    // pending tag changes (new generation, abandoned tag, or successful
    // tagging). Arming is per-tag and is only granted later, when we
    // actually observe the canonical new-chat empty state.
    $: {
        const pid = $pendingSyllabusTag ? ($pendingSyllabusTag.requestId || '__unset__') : null;
        if ($pendingSyllabusTag) {
            armStaleTimer();
            if (armedRequestId !== pid) {
                // New pending tag — start un-armed; arming happens in the
                // observation block below once we see chatId='' && pathname='/'.
                armedForNewChat = false;
                armedRequestId = pid;
            }
        } else {
            clearStaleTimer();
            armedForNewChat = false;
            armedRequestId = null;
        }
    }

    // Arming observer: when a pending tag exists, $chatId is empty, and we
    // are on the canonical new-chat page ('/'), arm the success block. This
    // state is on the legitimate path for BOTH:
    //   - cache miss from '/'           (already on '/' with chatId=='' at click)
    //   - cache miss from /c/<existing> (reached after goto('/?q=...') clears chatId)
    // A user navigating to /c/<other> mid-flight goes directly to /c/<other>
    // and never traverses this state, so arming never fires for that flow.
    //
    // Symmetric disarm: if the user later leaves '/' (e.g. clicks a sidebar
    // chat after arming but before the new chat is created), disarm. This
    // closes a corner case where chatId updates in the same tick as the
    // navigation to /c/<other> and both route guards happen to miss — the
    // pending tag would otherwise persist with armed=true and could falsely
    // tag a future new chat the user submits from '/'.
    $: if ($pendingSyllabusTag && $page && $page.url) {
        const onRoot = $page.url.pathname === '/';
        if (onRoot && !$chatId && !armedForNewChat) {
            armedForNewChat = true;
        } else if (!onRoot && armedForNewChat) {
            armedForNewChat = false;
        }
    }

    // Successful path: chatId becomes a real id for the NEW chat => tag it,
    // then clear. This must run BEFORE the route guard below to avoid a race
    // when the route also changes to /c/<id> at the same tick.
    //
    // Guards:
    //   - originChatId guard: $chatId must differ from the click-time chat id.
    //     Catches the /c/<existing> intra-tick race where $chatId still holds
    //     the pre-existing id before goto('/?q=...') resets it.
    //   - armedForNewChat guard: we must have observed the canonical new-chat
    //     empty state (chatId='' on '/') for THIS pending tag. Catches the
    //     case where the user clicks an unrelated sidebar chat /c/<other>
    //     between pendingSyllabusTag.set(...) and new-chat persistence —
    //     $chatId would become <other> (≠ originChatId) but arming never
    //     happened, so we refuse to tag.
    //   - pathname === '/' at success tick: Open WebUI assigns the new chatId
    //     while still on '/' (before goto('/c/<new>')), so the legit success
    //     reactive tick sees pathname='/'. A late /c/<other> click after arming
    //     would be processed with pathname='/c/<other>', failing this check.
    $: if (
        $chatId &&
        $chatId !== lastTaggedChatId &&
        $pendingSyllabusTag &&
        $user &&
        $chatId !== ($pendingSyllabusTag.originChatId || '') &&
        armedForNewChat &&
        $page &&
        $page.url &&
        $page.url.pathname === '/'
    ) {
        lastTaggedChatId = $chatId;
        tagChat($chatId, $user.id, $pendingSyllabusTag);
        pendingSyllabusTag.set(null);
    }

    // Route guard A: chatId is empty but pathname has moved to a route that
    // is neither the canonical new-chat page ('/') nor the originPathname
    // (the /c/<existing> we clicked from — Open WebUI may clear $chatId a
    // tick before the SvelteKit URL transitions to '/' on the /?q=... flow,
    // and we must not treat that intermediate state as a user-initiated
    // navigation away). Any other pathname means the user abandoned the
    // generation — clear the tag.
    $: if (
        $pendingSyllabusTag &&
        !$chatId &&
        $page &&
        $page.url &&
        $page.url.pathname !== '/' &&
        $page.url.pathname !== ($pendingSyllabusTag.originPathname || '')
    ) {
        console.log('[Ext] Pending syllabus tag abandoned (route changed to', $page.url.pathname, '), clearing.');
        pendingSyllabusTag.set(null);
    }

    // Route guard B: chatId has become a non-empty, non-origin value WHILE
    // arming never happened (i.e. we never traversed the canonical new-chat
    // empty state for this pending tag). This means the user navigated
    // directly to some other existing chat (e.g. /c/<other>) without ever
    // passing through '/'. Clearing the tag here prevents it from sitting in
    // the store and falsely tagging a future new chat with stale metadata
    // (e.g. if the user then submits a new prompt from '/').
    //
    // We deliberately do NOT clear when armedForNewChat is true: in that
    // case the success block above is the right place to handle the
    // transition (it will either tag the new chat on '/' or be guarded out
    // by the pathname check, and the route guard for the post-arm /c/<other>
    // path is route guard A above, which runs while chatId is still empty).
    $: if (
        $pendingSyllabusTag &&
        $chatId &&
        $chatId !== ($pendingSyllabusTag.originChatId || '') &&
        !armedForNewChat
    ) {
        console.log('[Ext] Pending syllabus tag abandoned (chatId jumped to', $chatId, 'without arming), clearing.');
        pendingSyllabusTag.set(null);
    }

    // LOW-12: Clear any pending syllabus tag when the user logs out (the
    // store flips $user to a falsy value). Without this, a tag armed by user
    // A could in principle outlive their session in the same browser tab and
    // be applied to a chat created after user B signs in. With server-side
    // user derivation in place (HIGH-1) the chat would still be tagged to
    // user B on the server, but the metadata would be wrong — clearing here
    // avoids that mis-attribution entirely.
    $: if (!$user && $pendingSyllabusTag) {
        console.log('[Ext] User logged out — clearing pending syllabus tag.');
        pendingSyllabusTag.set(null);
    }

    onDestroy(() => {
        clearStaleTimer();
        // Best-effort cleanup: a long-lived pending tag should not survive
        // component teardown (page navigation away from the app, hot reload).
        pendingSyllabusTag.set(null);
    });

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