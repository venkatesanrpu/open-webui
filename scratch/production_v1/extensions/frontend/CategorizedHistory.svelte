<script>
    import { onMount } from 'svelte';
    import { user, chats } from '$lib/stores';
    import { goto } from '$app/navigation';
    import { showSidebar, mobile } from '$lib/stores';

    let syllabusMeta = [];
    let taggedChats = [];
    let loading = true;

    onMount(async () => {
        await loadData();
    });

    // Reload when chats update (e.g., after a new chat is created)
    $: if ($chats && $user) {
        loadData();
    }

    async function loadData() {
        if (!$user) return;

        // 1. Fetch the permanent syllabus structure
        try {
            const metaRes = await fetch('/api/ext/syllabus/meta');
            if (metaRes.ok) {
                syllabusMeta = await metaRes.json();
            }
        } catch (e) {
            console.error('[Ext] Failed to load syllabus meta', e);
        }

        // 2. Fetch the user's tagged chats
        try {
            const tagRes = await fetch(`/api/ext/history/tags/${$user.id}`);
            if (tagRes.ok) {
                const data = await tagRes.json();
                taggedChats = data.tags || [];
            }
        } catch (e) {
            console.error('[Ext] Failed to load tags', e);
        }

        loading = false;
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

    // Format a function name for display
    const formatFunction = (fn) => {
        if (fn === 'mcq_widget') return '❓ MCQ';
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
                    {formatFolderName(syllabus._exam_folder || syllabus.exam || 'Exam')}
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
                                                    <span class="truncate">{formatFunction(chat.data_function)} {chat.concept}</span>
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
