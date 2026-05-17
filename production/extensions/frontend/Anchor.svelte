<script>
    import SyllabusSidebarMenu from './SyllabusSidebarMenu.svelte';
    import CategorizedHistory from './CategorizedHistory.svelte';
    import HistoryTracker from './HistoryTracker.svelte';
    import StudyPanel from './StudyPanel.svelte';
    import { studyPanelOpen } from './syllabusStore.js';

    let activeTab = 'syllabus'; // 'syllabus' | 'history'
</script>

<!--
    Anchor.svelte — Custom extension injection point in the native Sidebar.

    Renders:
      1. HistoryTracker      — headless; tags new chats with syllabus metadata.
      2. Study Materials btn — opens the full-viewport StudyPanel modal.
      3. Tab switcher        — 📚 Syllabus | 📋 History
      4. SyllabusSidebarMenu — content tree (Syllabus tab).
      5. CategorizedHistory  — past chats grouped by syllabus (History tab).
      6. StudyPanel          — modal mounted via portal at document.body.
-->
<div class="custom-extensions-anchor pb-2">
    <!-- Headless — manages HistoryTracker race-condition guards -->
    <HistoryTracker />

    <!-- Study Materials launcher — always visible above the tabs -->
    <button
        on:click={() => studyPanelOpen.set(true)}
        class="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-xl
               text-sm font-medium text-gray-700 dark:text-gray-300
               hover:bg-gray-100 dark:hover:bg-gray-900 transition-colors"
    >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
             stroke-width="2" stroke="currentColor"
             class="size-4 text-blue-500 flex-shrink-0">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
        </svg>
        <span>Study Materials</span>
    </button>

    <!-- Tab switcher -->
    <div class="flex mx-2 mt-1 mb-1 bg-gray-100 dark:bg-gray-850 rounded-lg p-0.5">
        <button
            on:click={() => activeTab = 'syllabus'}
            class="flex-1 text-[11px] font-medium py-1.5 rounded-md transition-all
                {activeTab === 'syllabus'
                    ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
        >
            📚 Syllabus
        </button>
        <button
            on:click={() => activeTab = 'history'}
            class="flex-1 text-[11px] font-medium py-1.5 rounded-md transition-all
                {activeTab === 'history'
                    ? 'bg-white dark:bg-gray-800 text-purple-600 dark:text-purple-400 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
        >
            📋 History
        </button>
    </div>

    <!-- Tab content -->
    {#if activeTab === 'syllabus'}
        <SyllabusSidebarMenu />
    {:else}
        <CategorizedHistory />
    {/if}

    <!-- Modal — rendered at document.body via portal action in StudyPanel.svelte -->
    <StudyPanel />
</div>
