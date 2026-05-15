<script>
    import { chatId, user } from '$lib/stores';
    import { pendingSyllabusTag } from './syllabusStore.js';

    // Track the last chat ID we tagged to prevent duplicate tagging
    let lastTaggedChatId = '';

    // This reactive block fires when Open WebUI's native $chatId store updates.
    // $chatId is set AFTER the LLM response completes and the chat is persisted.
    $: if ($chatId && $chatId !== lastTaggedChatId && $pendingSyllabusTag && $user) {
        lastTaggedChatId = $chatId;
        tagChat($chatId, $user.id, $pendingSyllabusTag);
        pendingSyllabusTag.set(null);
    }

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
