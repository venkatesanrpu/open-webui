<script>
    import { onMount } from 'svelte';
    import { user, chats } from '$lib/stores';
    import { goto } from '$app/navigation';
    import { showSidebar, mobile } from '$lib/stores';

    let syllabusMeta = [];
    let taggedChats = [];
    let loading = true;
    let metaLoaded = false;

    onMount(async () => {
        await loadMeta();
        await loadTags();
        loading = false;
    });

    // Reload TAGS only when chats update (e.g., after a new chat is created).
    // Syllabus meta is static on disk; refetching it on every $chats change
    // is wasted I/O and re-triggers full re-render of nested <details> trees.
    // Meta is loaded once on mount; an explicit reloadMeta() entry point is
    // exported for callers that need to invalidate it.
    $: if ($chats && $user && metaLoaded) {
        loadTags();
    }

    async function loadMeta() {
        try {
            const metaRes = await fetch('/api/ext/syllabus/meta');
            if (metaRes.ok) {
                const raw = await metaRes.json();
                syllabusMeta = Array.isArray(raw) ? raw.flatMap(normalizeSyllabus) : [];
            }
        } catch (e) {
            console.error('[Ext] Failed to load syllabus meta', e);
        } finally {
            metaLoaded = true;
        }
    }

    // Normalize legacy (flat: subject/topics at root) and current
    // (nested: exam + subjects:[{subject, topics}]) syllabus shapes into a
    // single flat array of { exam, exam_key, subject, topics, _exam_folder }
    // rows that the existing template can render without further branching.
    function normalizeSyllabus(s) {
        if (!s || typeof s !== 'object') return [];
        const examLabel = s.exam || s._exam_folder || '';
        const examKey = s.exam_key || '';
        const folder = s._exam_folder || examLabel;
        const subjects = Array.isArray(s.subjects) && s.subjects.length
            ? s.subjects
            : [{ subject: s.subject, subject_key: s.subject_key, topics: s.topics || [] }];
        return subjects.map(sub => ({
            exam: examLabel,
            exam_key: examKey,
            _exam_folder: folder,
            subject: sub.subject,
            subject_key: sub.subject_key,
            topics: sub.topics || []
        }));
    }

    async function loadTags() {
        if (!$user) return;
        try {
            const tagRes = await fetch(`/api/ext/history/tags/${$user.id}`);
            if (tagRes.ok) {
                const data = await tagRes.json();
                taggedChats = data.tags || [];
            }
        } catch (e) {
            console.error('[Ext] Failed to load tags', e);
        }
    }

    // Exposed for future "force refresh meta" affordances; intentionally
    // unused right now so meta truly loads once per session.
    // eslint-disable-next-line no-unused-vars
    export async function reloadMeta() {
        metaLoaded = false;
        await loadMeta();
    }

    // Match using lesson_key from syllabus.json against lesson field in ext_chat_tags
    // Both are now snake_case (e.g., "tensor_analysis") since user standardized data-lesson
    function getChatsForLesson(topicKey, lessonKey) {
        return taggedChats.filter(t =>
            t.topic === topicKey && t.lesson === lessonKey
        );
    }

    function countChatsForTopic(topicKey) {
        return taggedChats.filter(t => t.topic === topicKey).length;
    }

    // Get untagged "General" chats (typed directly by user, not via syllabus)
    function getGeneralChats() {
        if (!$chats) return [];
        const taggedIds = new Set(taggedChats.map(t => t.chat_id));
        return $chats.filter(c => !taggedIds.has(c.id));
    }

    const openChat = (id) => {
        goto(`/c/${id}`);
        if ($mobile) showSidebar.set(false);
    };

    const formatFolderName = (name) => {
        return name.replace(/_/g, ' ');
    };

    // Title-case a level token (e.g., "basic" -> "Basic"). Empty/nullish -> "".
    const formatLevel = (lvl) => {
        if (!lvl) return '';
        const s = String(lvl).trim();
        if (!s) return '';
        return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
    };

    // Format a chat row's leading label. MCQ rows prepend the level when present
    // so users can distinguish basic/intermediate/advanced variants of the same
    // concept; notes and legacy MCQ rows (no level) keep the original label.
    const formatChatLabel = (chat) => {
        const fn = chat.data_function;
        if (fn === 'mcq_widget') {
            const lvl = formatLevel(chat.level);
            return lvl ? `❓ ${lvl} MCQ` : '❓ MCQ';
        }
        if (fn === 'ask_agent') return '📝 Notes';
        return fn;
    };
</script>

<div class="mt-1 pb-2">
    {#if loading}
        <div class="text-[11px] text-gray-500 px-4 py-2">Loading...</div>
    {:else if syllabusMeta.length === 0}
        <div class="text-[11px] text-gray-500 px-4 py-2 italic">No syllabus data found.</div>
    {:else}
        <!-- Render each discovered syllabus -->
        {#each syllabusMeta as syllabus}
            <details class="group/exam ml-1 mt-1">
                <summary class="text-[11px] font-bold text-gray-700 dark:text-gray-300 cursor-pointer hover:text-purple-600 dark:hover:text-purple-400 py-0.5 uppercase tracking-wide">
                    {formatFolderName(syllabus.exam || syllabus._exam_folder || 'Exam')}
                </summary>

                <!-- Subject -->
                <div class="ml-2 pl-2 border-l border-purple-200 dark:border-purple-800/50">
                    <div class="text-[10px] font-semibold text-purple-600 dark:text-purple-400 py-0.5 mb-0.5">
                        {syllabus.subject || 'Subject'}
                    </div>

                    <!-- Topics -->
                    {#each (syllabus.topics || []) as topic}
                        {@const topicChatCount = countChatsForTopic(topic.topic_key)}
                        <details class="group/topic ml-1 pl-2 border-l border-gray-200 dark:border-gray-800 mt-0.5">
                            <summary class="text-[10px] text-gray-600 dark:text-gray-400 cursor-pointer hover:text-gray-900 dark:hover:text-white py-0.5 flex items-center gap-1">
                                <span class="truncate">{topic.topic}</span>
                                {#if topicChatCount > 0}
                                    <span class="text-[8px] bg-purple-100 dark:bg-purple-900/40 text-purple-600 dark:text-purple-400 px-1 rounded-full flex-shrink-0">{topicChatCount}</span>
                                {/if}
                            </summary>

                            <!-- Lessons -->
                            {#each (topic.lessons || []) as lesson}
                                {@const lessonChats = getChatsForLesson(topic.topic_key, lesson.lesson_key)}
                                <details class="group/lesson ml-1 pl-2 border-l border-gray-100 dark:border-gray-800/40 mt-0.5">
                                    <summary class="text-[9px] text-gray-500 dark:text-gray-500 cursor-pointer hover:text-gray-900 dark:hover:text-white py-0.5 flex items-center gap-1">
                                        <span class="truncate">{lesson.lesson}</span>
                                        {#if lessonChats.length > 0}
                                            <span class="text-[8px] bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400 px-1 rounded-full flex-shrink-0">{lessonChats.length}</span>
                                        {/if}
                                    </summary>

                                    <div class="ml-1 mt-0.5 space-y-0.5">
                                        {#if lessonChats.length === 0}
                                            <div class="text-[8px] text-gray-400 dark:text-gray-600 italic px-1">—</div>
                                        {:else}
                                            {#each lessonChats as chat}
                                                <button
                                                    on:click={() => openChat(chat.chat_id)}
                                                    class="w-full text-left px-1.5 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-[9px] text-gray-600 dark:text-gray-400 transition flex items-center gap-1"
                                                >
                                                    <span class="truncate">{formatChatLabel(chat)} {chat.concept}</span>
                                                </button>
                                            {/each}
                                        {/if}
                                    </div>
                                </details>
                            {/each}
                        </details>
                    {/each}
                </div>
            </details>
        {/each}

        <!-- General Chats (untagged) -->
        {@const generalChats = getGeneralChats()}
        {#if generalChats.length > 0}
            <details class="group/general ml-1 pl-2 border-l border-gray-200 dark:border-gray-800 mt-2">
                <summary class="text-[11px] font-semibold text-gray-500 dark:text-gray-500 cursor-pointer hover:text-gray-900 dark:hover:text-white py-0.5">
                    General ({generalChats.length})
                </summary>
                <div class="mt-0.5 space-y-0.5 ml-1">
                    {#each generalChats as chat}
                        <button
                            on:click={() => openChat(chat.id)}
                            class="w-full text-left px-1.5 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-[9px] text-gray-500 dark:text-gray-500 transition truncate"
                        >
                            {chat.title || 'New Chat'}
                        </button>
                    {/each}
                </div>
            </details>
        {/if}
    {/if}
</div>
